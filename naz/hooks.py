import abc
import logging
import typing

from . import log

if typing.TYPE_CHECKING:
    from . import state  # noqa: F401


class BaseHook(abc.ABC):
    """
    Interface that must be implemented to satisfy naz's hooks.
    User implementations should inherit this class and
    implement the :func:`request <BaseHook.request>` and :func:`response <BaseHook.response>` methods with the type signatures shown.

    A hook is class with methods that are called just before a request is sent to SMSC and
    just after a response is received from SMSC.
    """

    @abc.abstractmethod
    async def request(self, smpp_command: str, log_id: str, hook_metadata: str) -> None:
        """
        called before a request is sent to SMSC.

        Parameters:
            smpp_command: any one of the SMSC commands eg submit_sm
            log_id: an ID that a user's application had previously supplied to naz to track/correlate different messages.
            hook_metadata: a string that a user's application had previously supplied to naz that it may want to be correlated with the log_id.
        """
        raise NotImplementedError("request method must be implemented.")

    @abc.abstractmethod
    async def response(
        self,
        smpp_command: str,
        log_id: str,
        hook_metadata: str,
        smsc_response: "state.CommandStatus",
    ) -> None:
        """
        called after a response is received from SMSC.

        Parameters:
            smpp_command: any one of the SMSC commands eg submit_sm_resp
            log_id: an ID that a user's application had previously supplied to naz to track/correlate different messages.
            hook_metadata: a string that a user's application had previously supplied to naz that it may want to be correlated with the log_id.
            smsc_response: the response from SMSC.
        """
        raise NotImplementedError("response method must be implemented.")


class SimpleHook(BaseHook):
    """
    This is an implementation of BaseHook.
    When this class is called by naz, it just logs the request or response.
    """

    def __init__(self, logger: typing.Union[None, log.BaseLogger] = None) -> None:
        if not isinstance(logger, (type(None), log.BaseLogger)):
            raise ValueError(
                "`logger` should be of type:: `None` or `naz.log.BaseLogger` You entered: {0}".format(
                    type(logger)
                )
            )

        if logger is not None:
            self.logger = logger
        else:
            self.logger = log.SimpleLogger("naz.SimpleHook")

    async def request(self, smpp_command: str, log_id: str, hook_metadata: str) -> None:
        self.logger.log(
            logging.NOTSET,
            {
                "event": "naz.SimpleHook.request",
                "stage": "start",
                "smpp_command": smpp_command,
                "log_id": log_id,
                "hook_metadata": hook_metadata,
            },
        )

    async def response(
        self,
        smpp_command: str,
        log_id: str,
        hook_metadata: str,
        smsc_response: "state.CommandStatus",
    ) -> None:
        self.logger.log(
            logging.NOTSET,
            {
                "event": "naz.SimpleHook.response",
                "stage": "start",
                "smpp_command": smpp_command,
                "log_id": log_id,
                "hook_metadata": hook_metadata,
                "smsc_response": smsc_response.description,
            },
        )
