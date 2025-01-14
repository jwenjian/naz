import abc
import time
import typing
import logging
import collections
from logging import handlers


class BaseLogger(abc.ABC):
    """
    Interface that must be implemented to satisfy naz's logger.
    User implementations should inherit this class and
    implement the :func:`bind <BaseLogger.bind>` and :func:`log <BaseLogger.log>` methods with the type signatures shown.

    A logger is class with methods that are called whenever naz wants to log something.
    This enables developers to implement logging in any way that they want.
    """

    @abc.abstractmethod
    def bind(self, level: typing.Union[str, int], log_metadata: dict) -> None:
        """
        called when a naz client is been instantiated so that the logger can be
        notified of loglevel & log_metadata that a user supplied to a naz client.
        The logger can choose to bind these log_metadata to itself.

        Parameters:
            loglevel: logging level eg DEBUG
            log_metadata: log metadata that can be included in all log statements
        """
        raise NotImplementedError("`bind` method must be implemented.")

    @abc.abstractmethod
    def log(self, level: typing.Union[str, int], log_data: dict) -> None:
        """
        called by naz everytime it wants to log something.

        Parameters:
            level: logging level eg `logging.INFO`
            log_data: the message to log
        """
        raise NotImplementedError("`log` method must be implemented.")


class SimpleLogger(BaseLogger):
    """
    This is an implementation of BaseLogger.
    It implements a structured logger that renders logs as a dict.

    example usage:

    .. highlight:: python
    .. code-block:: python

        logger = SimpleLogger("myLogger")
        logger.bind(level="INFO",
                    log_metadata={"customer_id": "34541"})
        logger.log(logging.INFO,
                   {"event": "web_request", "url": "https://www.google.com/"})
    """

    def __init__(self, logger_name: str, handler: logging.Handler = logging.StreamHandler()):
        """
        Parameters:
            logger_name: name of the logger. it should be unique per logger.
        """
        if not isinstance(logger_name, str):
            raise ValueError(
                "`logger_name` should be of type:: `str` You entered: {0}".format(type(logger_name))
            )
        if not isinstance(handler, logging.Handler):
            raise ValueError(
                "`handler` should be of type:: `logging.Handler` You entered: {0}".format(
                    type(handler)
                )
            )

        self.logger_name = logger_name
        self.handler = handler
        self.logger: typing.Union[None, logging.LoggerAdapter] = None

    def bind(self, level: typing.Union[str, int], log_metadata: dict) -> None:
        level = self._nameToLevel(level=level)

        self._logger = logging.getLogger(self.logger_name)
        formatter = logging.Formatter("%(message)s")
        self.handler.setFormatter(formatter)
        self.handler.setLevel(level)
        if not self._logger.handlers:
            self._logger.addHandler(self.handler)
        self._logger.setLevel(level)
        self.logger = _NazLoggingAdapter(self._logger, log_metadata)

    def log(self, level: typing.Union[str, int], log_data: typing.Union[str, dict]) -> None:
        level = self._nameToLevel(level=level)

        if not self.logger:
            self.bind(level=level, log_metadata={})
        if typing.TYPE_CHECKING:
            # make mypy happy; https://github.com/python/mypy/issues/4805
            assert isinstance(self.logger, logging.LoggerAdapter)

        if level >= logging.ERROR:
            self.logger.log(level, log_data, exc_info=True)
        else:
            self.logger.log(level, log_data)

    @staticmethod
    def _nameToLevel(level: typing.Union[str, int]) -> int:
        try:
            if isinstance(level, str):
                # please mypy
                _level: int = logging._nameToLevel[level.upper()]
            else:
                _level = level
            return _level
        except KeyError as e:
            raise ValueError(
                "`level` should be one of; 'NOTSET', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'"
            ) from e


class _NazLoggingAdapter(logging.LoggerAdapter):
    _converter = time.localtime
    _formatter = logging.Formatter()

    def process(self, msg, kwargs):
        timestamp = self.formatTime()

        if isinstance(msg, str):
            merged_msg = "{0} {1} {2}".format(timestamp, msg, self.extra)
            if self.extra == {}:
                merged_msg = "{0} {1}".format(timestamp, msg)
            return merged_msg, kwargs
        else:
            _timestamp = {"timestamp": timestamp}
            # _timestamp should appear first in resulting dict
            merged_msg = {**_timestamp, **msg, **self.extra}
            return "{0}".format(merged_msg), kwargs

    def formatTime(self):
        """
        Return the creation time of the specified log event as formatted text.

        This code is borrowed from:
        https://docs.python.org/3/library/logging.html#logging.Formatter.formatTime

        The basic behaviour is as follows: an ISO8601-like (or RFC 3339-like) format is used.
        This function uses `time.localtime()` to convert the creation time to a tuple.
        """
        now = time.time()
        msecs = (now - int(now)) * 1000

        ct = self._converter(now)
        t = time.strftime(self._formatter.default_time_format, ct)
        s = self._formatter.default_msec_format % (t, msecs)
        return s


class BreachHandler(handlers.MemoryHandler):
    """
    This is an implementation of `logging.Handler` that puts logs in an in-memory ring buffer.
    When a trigger condition(eg a certain log level) is met;
    then all the logs in the buffer are flushed into a given stream(file, stdout etc)

    It is a bit like
    `logging.handlers.MemoryHandler <https://docs.python.org/3.6/library/logging.handlers.html#logging.handlers.MemoryHandler>`_
    except that it does not flush when the ring-buffer capacity is met but only when/if the trigger is met.

    It is inspired by the article
    `Triggering Diagnostic Logging on Exception <https://tersesystems.com/blog/2019/07/28/triggering-diagnostic-logging-on-exception/>`_

    example usage:

    .. highlight:: python
    .. code-block:: python

        import naz, logging

        _handler = naz.log.BreachHandler()
        logger = naz.log.SimpleLogger("aha", handler=_handler)
        logger.bind(level="INFO", log_metadata={"id": "123"})

        logger.log(logging.INFO, {"name": "Jayz"})
        logger.log(logging.ERROR, {"msg": "Houston, we got 99 problems."})

        # or alternatively, to use it with python stdlib logger
        logger = logging.getLogger("my-logger")
        handler = naz.log.BreachHandler()
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        handler.setLevel("DEBUG")
        if not logger.handlers:
            logger.addHandler(handler)
        logger.setLevel("DEBUG")

        logger.info("I did records for Tweet before y'all could even tweet - Dr. Missy Elliot")
        logger.error("damn")
    """

    def __init__(
        self,
        flushLevel=logging.WARNING,
        capacity=10_000,
        target=logging.StreamHandler(),
        flushOnClose=False,
    ):
        """
        Parameters:
            flushLevel: the log level that will trigger this handler to flush logs to :py:attr:`~target`
            capacity: the maximum number of log records to store in the ring buffer
            target: the ultimate `log handler <https://docs.python.org/3.6/library/logging.html#logging.Handler>`_ that will be used.
            flushOnClose: whether to flush the buffer when the handler is closed even if the flush level hasn't been exceeded
        """
        # call `logging.handlers.MemoryHandler` init
        super(BreachHandler, self).__init__(
            capacity=capacity,
            flushLevel=flushLevel,
            target=target,
            flushOnClose=flushOnClose,  # pytype: disable=wrong-keyword-args
        )
        self.buffer = collections.deque(maxlen=self.capacity)  # pytype: disable=attribute-error
        # assuming each log record is 250 bytes, then the maximum
        # memory used by `buffer` will always be == 250*10_000/(1000*1000) == 2.5MB

    def shouldFlush(self, record):
        """
        Check for record at the flushLevel or higher.
        Implementation is mostly taken from `logging.handlers.MemoryHandler`
        """
        return record.levelno >= self.flushLevel  # pytype: disable=attribute-error
