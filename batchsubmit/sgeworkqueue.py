
import backend
import sge
from workqueue import WorkQueue, Task
from workqueue import WORK_QUEUE_SCHEDULE_FCFS, WORK_QUEUE_SCHEDULE_FILES, WORK_QUEUE_WORKER_MODE_SHARED, WORK_QUEUE_MASTER_MODE_STANDALONE
from workqueue import set_debug_flag

import os


class SGEWorkQueue(sge.SGE):
    """
    Generates a workflow using for SGE, but uses WorkQueue to run the jobs.
    The master user can then have multiple accounts submit workers for the jobs.
    """


    def __init__(self, *args, **kws):

        port        = kws.pop('port', 9123)
        master_name = kws.pop('name', 'bs.sge.wq')
        catalog     = kws.pop('catalog', True)
        exclusive   = kws.pop('exclusive', False)
        wq_alg      = kws.pop('wq_alg', WORK_QUEUE_SCHEDULE_FCFS)

        wq_debug    = kws.pop('ccl_debug', 'all')
        set_debug_flag(wq_debug)

        backend.Backend.__init__(self, *args, **kws)

        self.workqueue = WorkQueue(port=port,name=master_name, catalog=catalog, exclusive=exclusive)
        self.workqueue.specify_algorithm(wq_alg)

        # self.workqueue.specify_master_mode(WORK_QUEUE_MASTER_MODE_STANDALONE)
        self.workqueue.specify_worker_mode(WORK_QUEUE_WORKER_MODE_SHARED)


        
    def create_task(self, jobfile):
        """
        Creates a Task to execute the specified jobfile
        """

        job = os.path.basename(jobfile)

        cmd = '%(jobfile)s' % {
            # 'workarea' : self.workarea,
            'jobfile'  : jobfile }

        print 'Task Command:', cmd

        t = Task(cmd)
        t.tag = job

        return t

    def submit_jobs(self, jobfiles, **kws):
        """
        Creates Tasks for the jobfiles and submits them to the WorkQueue
        """

        for job in jobfiles:
            task = self.create_task(job)
            self.workqueue.submit(task)


    def is_job_running(self):
        return not self.workqueue.empty()

    def wait(self, **kws):
        """
        Wait for an SGE job to finish. Raises a *BackendError* if *max_tries* is exceeded.
        Key words:
          *poll_interval* : how long to wait between tries. Format: <time><units> where <units>
                            can be one of s, m, h, d, w for seconds, minutes, hours, days, weeks respectively
                            Default = 1m
          *max_tries*     : number of iterations to wait before giving up.
                            Default = infinity

        Returns: Boolean indicating if any task failed
        """

        poll_interval = kws.get('poll_interval', '1m')
        max_tries     = kws.get('max_tries', float('inf'))

        sleeptime     = self.parse_time_units(poll_interval)

        tries         = 0

        success = True

        while True:
            if not self.is_job_running():
                break
            if tries > max_tries:
                break

            task   = self.workqueue.wait(sleeptime)

            print '\tinit:', self.workqueue.stats.workers_init
            print '\tready:', self.workqueue.stats.workers_ready
            print '\tbusy:', self.workqueue.stats.workers_busy
            print '\trunning:', self.workqueue.stats.tasks_running
            print '\twaiting:', self.workqueue.stats.tasks_waiting
            print '\tcomplete:', self.workqueue.stats.tasks_complete

            if task:
                print 'Job %s finished with %s' % (task.tag, task.return_status)
                print '++++++++++++++++++++++++++++++', 'JOB OUTPUT: %s' % task.tag, '++++++++++++++++++++++++++++++'
                print task.output.strip()
                print '================================================================================'
                success = success and task.return_status == 0

                if not task.return_status == 0:
                    self.workqueue.submit(task)
                    tries += 1

        return success


    def job_preamble(self, **kws):
        return '#!/usr/bin/env bash'

    def job_conclusion(self, **kws):
        return """\
if [ $? -eq 0 ]; then
    echo DONE
else
    echo FAILURE
fi
"""
