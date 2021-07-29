"""
   Copyright 2021 InfAI (CC SES)

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""

__all__ = ("Jobs",)


from ..logger import getLogger
from .. import weibull
from .. import models
from . import DB, Data
import threading
import queue
import typing
import uuid
import datetime
import json
import time
import multiprocessing
import signal
import sys


logger = getLogger(__name__.split(".", 1)[-1])


def handle_sigterm(signo, stack_frame):
    logger.debug("got signal '{}' - exiting ...".format(signo))
    sys.exit(0)


# temporary workaround for code not supporting chunked data --->
class ConcatenatedFile:
    def __init__(self, files):
        self.__chunks = files

    def __read(self, n=65536):
        for chunk in self.__chunks:
            file = open(chunk, "rb")
            buffer = file.read(n)
            while buffer:
                yield buffer
                buffer = file.read(n)
            file.close()

    def build_input(self):
        path = "/data_cache/{}".format(uuid.uuid4().hex)
        with open(path, "wb") as file:
            for buffer in self.__read():
                file.write(buffer)
        return path
# <-------------------------------------------------------------


class Result:
    def __init__(self):
        self.weibull_item: typing.Optional[models.Weibull] = None
        self.job: typing.Optional[models.Job] = None
        self.error = False


class Worker(multiprocessing.Process):
    def __init__(self, job: models.Job, weibull_item: models.Weibull, data_handler: Data):
        super().__init__(name="jobs-worker-{}".format(job.id), daemon=True)
        self.__weibull_item = weibull_item
        self.__data_handler = data_handler
        self.__job = job
        self.result = multiprocessing.Queue()

    def run(self) -> None:
        signal.signal(signal.SIGTERM, handle_sigterm)
        signal.signal(signal.SIGINT, handle_sigterm)
        result_obj = Result()
        try:
            logger.debug("starting job '{}' ...".format(self.__job.id))
            self.__job.status = models.JobStatus.running
            files, time_field, self.__weibull_item.data_checksum = self.__data_handler.get(source_id=self.__weibull_item.service_id)
            input_path = ConcatenatedFile(files=files).build_input()
            logger.debug(
                "{}: calculating weibull distribution for '{}' in '{}' ...".format(
                    self.__job.id, self.__weibull_item.config["target_error_code"],
                    self.__weibull_item.config["target_col"]
                )
            )
            self.__weibull_item.result = weibull.generate_weibull(
                df=weibull.df_from_csv(
                    csv_path=input_path,
                    time_col=time_field,
                    sorted=True
                ),
                errorcode_column=self.__weibull_item.config["target_col"],
                errorcode=self.__weibull_item.config["target_error_code"]
            )
            self.__weibull_item.created = "{}Z".format(datetime.datetime.utcnow().isoformat())
            result_obj.weibull_item = self.__weibull_item
            self.__job.status = models.JobStatus.finished
            logger.debug("{}: completed successfully".format(self.__job.id))
        except Exception as ex:
            self.__job.status = models.JobStatus.failed
            self.__job.reason = str(ex)
            logger.error("{}: failed - {}".format(self.__job.id, ex))
            result_obj.error = True
        result_obj.job = self.__job
        self.result.put(result_obj)


class Jobs(threading.Thread):
    def __init__(self, db_handler: DB, data_handler: Data, check_delay: typing.Union[int, float], max_jobs: int):
        super().__init__(name="jobs-handler", daemon=True)
        self.__db_handler = db_handler
        self.__data_handler = data_handler
        self.__check_delay = check_delay
        self.__max_jobs = max_jobs
        self.__job_queue = queue.Queue()
        self.__job_pool: typing.Dict[str, models.Job] = dict()
        self.__worker_pool: typing.Dict[str, Worker] = dict()

    def create(self, weibull_id: str) -> str:
        for job in self.__job_pool.values():
            if job.weibull_id == weibull_id:
                logger.debug("job for weibull ID '{}' already exists".format(weibull_id))
                return job.id
        job = models.Job(
            id=uuid.uuid4().hex,
            weibull_id=weibull_id,
            created="{}Z".format(datetime.datetime.utcnow().isoformat())
        )
        self.__job_pool[job.id] = job
        logger.debug("created job for weibull ID '{}'".format(weibull_id))
        self.__job_queue.put_nowait(job.id)
        return job.id

    def get_job(self, job_id: str) -> models.Job:
        return self.__job_pool[job_id]

    def list_jobs(self) -> list:
        return list(self.__job_pool.keys())

    def run(self):
        while True:
            try:
                if len(self.__worker_pool) < self.__max_jobs:
                    try:
                        job_id = self.__job_queue.get(timeout=self.__check_delay)
                        worker = Worker(
                            job=self.__job_pool[job_id],
                            weibull_item=models.Weibull(json.loads(self.__db_handler.get(b"weibull-", self.__job_pool[job_id].weibull_id.encode()))),
                            data_handler=self.__data_handler
                        )
                        self.__worker_pool[job_id] = worker
                        worker.start()
                    except queue.Empty:
                        pass
                else:
                    time.sleep(self.__check_delay)
                for job_id in list(self.__worker_pool.keys()):
                    if not self.__worker_pool[job_id].is_alive():
                        res = self.__worker_pool[job_id].result.get()
                        self.__db_handler.put(b"jobs-", res.job.id.encode(), json.dumps(dict(res.job)).encode())
                        if not res.error:
                            self.__db_handler.put(b"weibull-", res.weibull_item.id.encode(), json.dumps(dict(res.weibull_item)).encode())
                        self.__worker_pool[job_id].close()
                        del self.__worker_pool[job_id]
                        del self.__job_pool[job_id]
            except Exception as ex:
                logger.error("job handling failed - {}".format(ex))
