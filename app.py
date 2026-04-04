import os
import time
import uuid
import threading
import multiprocessing
from datetime import datetime
from queue import Queue, Empty

from flask import Flask, render_template, request, jsonify, Response
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from webdriver_manager.chrome import ChromeDriverManager

from scraper import run_scraper, log_listener

app = Flask(__name__)

# Pre-install ChromeDriver once on startup
print("Pre-installing ChromeDriver...")
DRIVER_PATH = ChromeDriverManager().install()
print(f"Driver installed at: {DRIVER_PATH}")

# APScheduler
scheduler = BackgroundScheduler()
scheduler.start()

# In-memory state for all jobs
# job_id -> { type, scheduled_time, instances, status, instance_results, logs, log_queue }
jobs = {}
jobs_lock = threading.Lock()


def _run_job(job_id, num_instances):
    """Execute a scraper job with N instances."""
    with jobs_lock:
        if job_id not in jobs:
            return
        jobs[job_id]['status'] = 'running'
        jobs[job_id]['started_at'] = datetime.now().isoformat()
        log_list = jobs[job_id]['logs']

    log_list.append(f"[{time.strftime('%H:%M:%S')}] Job {job_id[:8]} starting with {num_instances} instance(s)...")

    # Set up logging: use a multiprocessing queue + a thread to collect logs
    mp_log_queue = multiprocessing.Queue()

    # Also write to a log file
    os.makedirs("logs", exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    log_file_path = f"logs/job_{job_id[:8]}_{timestamp}.txt"

    # Log collector thread: reads from mp queue, appends to job logs list
    def collect_logs():
        while True:
            try:
                record = mp_log_queue.get(timeout=1)
                if record is None:
                    break
                plain = record['text']
                log_list.append(plain)
                # Also write to file
                try:
                    with open(log_file_path, "a", encoding="utf-8") as f:
                        f.write(plain + "\n")
                except:
                    pass
            except Empty:
                # Check if all processes are done
                if all_done.is_set():
                    # Drain remaining
                    while True:
                        try:
                            record = mp_log_queue.get_nowait()
                            if record is None:
                                break
                            log_list.append(record['text'])
                        except Empty:
                            break
                    break

    all_done = threading.Event()
    collector = threading.Thread(target=collect_logs, daemon=True)
    collector.start()

    stop_event = multiprocessing.Event()
    config = {'verbose': True, 'test': False}
    processes = []

    with jobs_lock:
        jobs[job_id]['stop_event'] = stop_event

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

    # Wait for all processes
    for inst_id, p in processes:
        p.join()
        with jobs_lock:
            inst_result = jobs[job_id]['instance_results'].get(inst_id, {})
            if inst_result.get('status') == 'running':
                inst_result['status'] = 'completed'

    # Signal log collector to stop
    all_done.set()
    mp_log_queue.put(None)
    collector.join(timeout=5)

    # Determine final job status
    with jobs_lock:
        found = any(
            r.get('status') == 'appointments_found'
            for r in jobs[job_id]['instance_results'].values()
        )
        jobs[job_id]['status'] = 'appointments_found' if found else 'completed'
        jobs[job_id]['finished_at'] = datetime.now().isoformat()

    log_list.append(f"[{time.strftime('%H:%M:%S')}] Job {job_id[:8]} finished. Status: {jobs[job_id]['status']}")


def schedule_job(job_id, job_type, run_at, num_instances, interval_minutes=None):
    """Schedule a job in APScheduler."""
    if job_type == 'once':
        trigger = DateTrigger(run_date=run_at)
    else:
        trigger = IntervalTrigger(minutes=interval_minutes, start_date=run_at)

    scheduler.add_job(
        _run_job,
        trigger=trigger,
        args=[job_id, num_instances],
        id=job_id,
        replace_existing=True,
    )


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
            'logs': [],
            'stop_event': None,
            'started_at': None,
            'finished_at': None,
        }

    # Run in background thread
    t = threading.Thread(target=_run_job, args=(job_id, num_instances), daemon=True)
    t.start()

    return jsonify({'job_id': job_id, 'status': 'starting'})


@app.route('/api/schedule', methods=['POST'])
def schedule():
    data = request.get_json() or {}
    job_type = data.get('type', 'once')  # 'once' or 'recurring'
    date_str = data.get('date')  # 'YYYY-MM-DD'
    time_str = data.get('time')  # 'HH:MM'
    num_instances = int(data.get('instances', 1))
    interval_minutes = data.get('interval_minutes')  # for recurring

    if not date_str or not time_str:
        return jsonify({'error': 'date and time are required'}), 400

    try:
        run_at = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except ValueError:
        return jsonify({'error': 'Invalid date/time format'}), 400

    if job_type == 'recurring' and not interval_minutes:
        return jsonify({'error': 'interval_minutes required for recurring jobs'}), 400

    job_id = str(uuid.uuid4())

    with jobs_lock:
        jobs[job_id] = {
            'type': job_type,
            'scheduled_time': run_at.isoformat(),
            'instances': num_instances,
            'status': 'scheduled',
            'instance_results': {},
            'logs': [],
            'stop_event': None,
            'started_at': None,
            'finished_at': None,
            'interval_minutes': interval_minutes if job_type == 'recurring' else None,
        }

    schedule_job(job_id, job_type, run_at, num_instances, interval_minutes)
    return jsonify({'job_id': job_id, 'status': 'scheduled', 'run_at': run_at.isoformat()})


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
                'interval_minutes': j.get('interval_minutes'),
            })
    # Sort: running first, then scheduled, then completed
    order = {'running': 0, 'starting': 1, 'scheduled': 2, 'completed': 3, 'appointments_found': 3, 'cancelled': 4}
    result.sort(key=lambda x: order.get(x['status'], 5))
    return jsonify(result)


@app.route('/api/jobs/<job_id>', methods=['DELETE'])
def cancel_job(job_id):
    with jobs_lock:
        if job_id not in jobs:
            return jsonify({'error': 'Job not found'}), 404
        job = jobs[job_id]
        if job['status'] == 'running':
            # Stop running instances
            if job.get('stop_event'):
                job['stop_event'].set()
            job['status'] = 'cancelled'
        elif job['status'] == 'scheduled':
            try:
                scheduler.remove_job(job_id)
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

            # Send new log lines
            if last_idx < len(current_logs):
                for line in current_logs[last_idx:]:
                    yield f"data: {line}\n\n"
                last_idx = len(current_logs)

            # If job is done, send final status and close
            if status in ('completed', 'appointments_found', 'cancelled'):
                yield f"event: done\ndata: {status}\n\n"
                return

            time.sleep(0.5)

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)
