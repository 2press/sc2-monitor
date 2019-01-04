import logging
import traceback

from sc2monitor.model import Log


class SQLAlchemyHandler(logging.Handler):

    def __init__(self, db_session):
        super().__init__()
        self.db_session = db_session

    def emit(self, record):
        trace = None
        exc = record.__dict__['exc_info']
        if exc:
            trace = traceback.format_exc()
        log = Log(
            logger=record.__dict__['name'],
            level=record.__dict__['levelname'],
            trace=trace,
            msg=record.__dict__['msg'],)
        self.db_session.add(log)
        self.db_session.commit()