import os
import time
import uuid
import threading
import multiprocessing
from datetime import datetime
from queue import Empty

from flask import Flask, render_template, request, jsonify, Response
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from webdriver_manager.chrome import ChromeDriverManager

from scraper import run_scraper

app = Flask(__name__)

# Pre-install ChromeDriver once on startup
print("Pre-installing ChromeDriver...")
DRIVER_PATH = ChromeDriverManager().install()
print(f"Driver installed at: {DRIVER_PATH}")

# APScheduler
scheduler = BackgroundScheduler()
scheduler.start()

# In-memory state for all jobs
# job_id -> { type, instances, status, instance_results, instance_times, logs, ... }
jobs = {}
jobs_lock = threading.Lock()


def _init_job_logging(job_id):
    """Set up shared logging infrastructure for a job. Returns (mp_log_queue, stop_event, cleanup_fn)."""
    with jobs_lock:
        job = jobs[job_id]
        log_list = job['logs']

    mp_log_queue = multiprocessing.Queue()
    stop_event = multiprocessing.Event()

    os.makedirs("logs", exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    log_file_path = f"logs/job_{job_id[:8]}_{timestamp}.txt"

    all_done = threading.Event()

    def collect_logs():
        while True:
            try:
                record = mp_log_queue.get(timeout=1)
                if record is None:
                    break
                plain = record['text']
                log_list.append(plain)
                try:
                    with open(log_file_path, "a", encoding="utf-8") as f:
                        f.write(plain + "\n")
                except:
                    pass
            except Empty:
                if all_done.is_set():
                    while True:
                        try:
                            record = mp_log_queue.get_nowait()
                            if record is None:
                                break
                            log_list.append(record['text'])
                        except Empty:
                            break
                    break

    collector = threading.Thread(target=collect_logs, daemon=True)
    collector.start()

    with jobs_lock:
        jobs[job_id]['stop_event'] = stop_event
        jobs[job_id]['_mp_log_queue'] = mp_log_queue
        jobs[job_id]['_all_done'] = all_done
        jobs[job_id]['_collector'] = collector

    return mp_log_queue, stop_event, all_done, collector


def _run_job(job_id, num_instances):
    """Execute a scraper job with N instances all starting now."""
    with jobs_lock:
        if job_id not in jobs:
            return
        jobs[job_id]['status'] = 'running'
        jobs[job_id]['started_at'] = datetime.now().isoformat()
        log_list = jobs[job_id]['logs']

    log_list.append(f"[{time.strftime('%H:%M:%S')}] Job {job_id[:8]} starting with {num_instances} instance(s)...")

    mp_log_queue, stop_event, all_done, collector = _init_job_logging(job_id)

    config = {'verbose': True, 'test': False}
    processes = []

    for i in range(num_instances):
        with jobs_lock:
            jobs[job_id]['instance_results'][i + 1] = {'status': 'running', 'attempts': 0, 'duration': 0}

        p = multiprocessing.Process(
            target=run_scraper,
            args=(i + 1, config, stop_event, DRIVER_PATH, mp_log_queue)
        )
        p.start()
        processes.append((i + 1, p))
        if i < num_instances - 1:
            time.sleep(1)

    for inst_id, p in processes:
        p.join()
        with jobs_lock:
            inst_result = jobs[job_id]['instance_results'].get(inst_id, {})
            if inst_result.get('status') == 'running':
                inst_result['status'] = 'completed'

    _finalize_job(job_id, all_done, mp_log_queue, collector)


def _finalize_job(job_id, all_done, mp_log_queue, collector):
    """Clean up logging and set final job status."""
    all_done.set()
    mp_log_queue.put(None)
    collector.join(timeout=5)

    with jobs_lock:
        if job_id not in jobs:
            return
        found = any(
            r.get('status') == 'appointments_found'
            for r in jobs[job_id]['instance_results'].values()
        )
        jobs[job_id]['status'] = 'appointments_found' if found else 'completed'
        jobs[job_id]['finished_at'] = datetime.now().isoformat()
        jobs[job_id]['logs'].append(
            f"[{time.strftime('%H:%M:%S')}] Job {job_id[:8]} finished. Status: {jobs[job_id]['status']}"
        )


def _launch_instance(job_id, instance_id):
    """Launch a single instance for a scheduled job. Called by APScheduler at the instance's scheduled time."""
    with jobs_lock:
        if job_id not in jobs:
            return
        job = jobs[job_id]
        # Mark job as running if it's still scheduled
        if job['status'] == 'scheduled':
            job['status'] = 'running'
            job['started_at'] = datetime.now().isoformat()
            # First instance to fire — set up shared logging
        job['instance_results'][instance_id] = {'status': 'running', 'attempts': 0, 'duration': 0}
        log_list = job['logs']

    log_list.append(f"[{time.strftime('%H:%M:%S')}] Instance {instance_id} starting...")

    # Get or create shared logging infrastructure
    with jobs_lock:
        mp_log_queue = job.get('_mp_log_queue')
        stop_event = job.get('stop_event')

    if mp_log_queue is None or stop_event is None:
        mp_log_queue, stop_event, all_done, collector = _init_job_logging(job_id)

    config = {'verbose': True, 'test': False}

    p = multiprocessing.Process(
        target=run_scraper,
        args=(instance_id, config, stop_event, DRIVER_PATH, mp_log_queue)
    )
    p.start()

    with jobs_lock:
        if '_processes' not in jobs[job_id]:
            jobs[job_id]['_processes'] = []
        jobs[job_id]['_processes'].append((instance_id, p))

    p.join()

    with jobs_lock:
        inst_result = jobs[job_id]['instance_results'].get(instance_id, {})
        if inst_result.get('status') == 'running':
            inst_result['status'] = 'completed'

        # Check if all instances are done
        total = jobs[job_id]['instances']
        finished = sum(1 for r in jobs[job_id]['instance_results'].values() if r.get('status') != 'running')

    if finished >= total:
        with jobs_lock:
            all_done = jobs[job_id].get('_all_done')
            collector = jobs[job_id].get('_collector')
        if all_done and collector:
            _finalize_job(job_id, all_done, mp_log_queue, collector)


# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/run-now', methods=['POST'])
def run_now():
    data = request.get_json() or {}
    num_instances = int(data.get('instances', 1))
    job_id = str(uuid.uuid4())

    with jobs_lock:
        jobs[job_id] = {
            'type': 'immediate',
            'scheduled_time': datetime.now().isoformat(),
            'instances': num_instances,
            'status': 'starting',
            'instance_results': {},
            'instance_times': {},
            'logs': [],
            'stop_event': None,
            'started_at': None,
            'finished_at': None,
        }

    t = threading.Thread(target=_run_job, args=(job_id, num_instances), daemon=True)
    t.start()

    return jsonify({'job_id': job_id, 'status': 'starting'})


@app.route('/api/schedule', methods=['POST'])
def schedule():
    data = request.get_json() or {}
    job_type = data.get('type', 'once')  # 'once' or 'recurring'
    date_str = data.get('date')  # 'YYYY-MM-DD'
    instance_times = data.get('instance_times', [])  # [{"id": 1, "time": "HH:MM"}, ...]
    interval_minutes = data.get('interval_minutes')  # for recurring

    if not date_str:
        return jsonify({'error': 'date is required'}), 400
    if not instance_times or len(instance_times) == 0:
        return jsonify({'error': 'At least one instance with a time is required'}), 400

    if job_type == 'recurring' and not interval_minutes:
        return jsonify({'error': 'interval_minutes required for recurring jobs'}), 400

    # Parse and validate all instance times
    parsed_times = {}
    for entry in instance_times:
        inst_id = int(entry.get('id', 1))
        t = entry.get('time')
        if not t:
            return jsonify({'error': f'Time missing for instance {inst_id}'}), 400
        try:
            run_at = datetime.strptime(f"{date_str} {t}", "%Y-%m-%d %H:%M")
        except ValueError:
            return jsonify({'error': f'Invalid time format for instance {inst_id}'}), 400
        parsed_times[inst_id] = run_at

    job_id = str(uuid.uuid4())
    num_instances = len(parsed_times)

    # Store human-readable instance times for display
    display_times = {str(k): v.strftime("%H:%M") for k, v in parsed_times.items()}

    with jobs_lock:
        jobs[job_id] = {
            'type': job_type,
            'scheduled_time': min(parsed_times.values()).isoformat(),
            'instances': num_instances,
            'status': 'scheduled',
            'instance_results': {},
            'instance_times': display_times,
            'logs': [],
            'stop_event': None,
            'started_at': None,
            'finished_at': None,
            'interval_minutes': interval_minutes if job_type == 'recurring' else None,
        }

    # Schedule each instance with its own trigger
    for inst_id, run_at in parsed_times.items():
        sched_id = f"{job_id}__inst{inst_id}"
        if job_type == 'once':
            trigger = DateTrigger(run_date=run_at)
        else:
            trigger = IntervalTrigger(minutes=int(interval_minutes), start_date=run_at)

        scheduler.add_job(
            _launch_instance,
            trigger=trigger,
            args=[job_id, inst_id],
            id=sched_id,
            replace_existing=True,
        )

    return jsonify({
        'job_id': job_id,
        'status': 'scheduled',
        'instance_times': display_times,
    })


@app.route('/api/jobs', methods=['GET'])
def list_jobs():
    with jobs_lock:
        result = []
        for jid, j in jobs.items():
            result.append({
                'job_id': jid,
                'type': j['type'],
                'scheduled_time': j['scheduled_time'],
                'instances': j['instances'],
                'status': j['status'],
                'started_at': j.get('started_at'),
                'finished_at': j.get('finished_at'),
                'instance_results': j['instance_results'],
                'instance_times': j.get('instance_times', {}),
                'interval_minutes': j.get('interval_minutes'),
            })
    order = {'running': 0, 'starting': 1, 'scheduled': 2, 'completed': 3, 'appointments_found': 3, 'cancelled': 4}
    result.sort(key=lambda x: order.get(x['status'], 5))
    return jsonify(result)


@app.route('/api/jobs/<job_id>', methods=['DELETE'])
def cancel_job(job_id):
    with jobs_lock:
        if job_id not in jobs:
            return jsonify({'error': 'Job not found'}), 404
        job = jobs[job_id]
        if job['status'] in ('running', 'starting'):
            if job.get('stop_event'):
                job['stop_event'].set()
            job['status'] = 'cancelled'
        elif job['status'] == 'scheduled':
            # Remove all per-instance scheduler jobs
            for inst_id in range(1, job['instances'] + 1):
                try:
                    scheduler.remove_job(f"{job_id}__inst{inst_id}")
                except:
                    pass
            job['status'] = 'cancelled'
        else:
            return jsonify({'error': 'Job already finished'}), 400

    return jsonify({'status': 'cancelled'})


@app.route('/api/logs/<job_id>')
def stream_logs(job_id):
    """SSE endpoint for streaming logs of a specific job."""
    def generate():
        last_idx = 0
        while True:
            with jobs_lock:
                if job_id not in jobs:
                    yield f"data: Job not found\n\n"
                    return
                job = jobs[job_id]
                current_logs = job['logs']
                status = job['status']

            if last_idx < len(current_logs):
                for line in current_logs[last_idx:]:
                    yield f"data: {line}\n\n"
                last_idx = len(current_logs)

            if status in ('completed', 'appointments_found', 'cancelled'):
                yield f"event: done\ndata: {status}\n\n"
                return

            time.sleep(0.5)

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
