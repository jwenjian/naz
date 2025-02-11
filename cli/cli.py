import os
import sys
import random
import string
import asyncio
import logging
import argparse

import naz

from .utils import sig, load

os.environ["PYTHONASYNCIODEBUG"] = "1"


def make_parser():
    """
    this is abstracted into its own method so that it is easier to test it.
    """
    parser = argparse.ArgumentParser(
        prog="naz",
        description="""naz is an async SMPP client.
                example usage:
                naz-cli \
                --client dotted.path.to.naz.Client.instance
                """,
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s {version}".format(version=naz.__version__.about["__version__"]),
        help="The currently installed naz version.",
    )
    parser.add_argument(
        "--client",
        required=True,
        help="The dotted path to a `naz.Client` instance. \
        eg: --client dotted.path.to.a.naz.Client.class.instance",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        required=False,
        default=False,
        help="""Whether we want to do a dry-run of the naz cli.
        This is typically only used by developers who are developing naz.
        eg: --dry-run""",
    )
    return parser


def main():
    """
    entrypoint of naz-cli app.
    """
    parser = make_parser()
    args = parser.parse_args()
    dry_run = args.dry_run
    client = args.client

    _client_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=17))
    logger = naz.log.SimpleLogger("naz.cli")
    try:
        logger.log(logging.INFO, "\n\n\t {} \n\n".format("Naz: the SMPP client."))
        logger.log(
            logging.INFO, {"event": "naz.cli.main", "stage": "start", "client_id": _client_id}
        )
        client = load.load_class(dotted_path=client, logger=logger)
        if dry_run:
            logger.log(
                logging.WARN,
                "\n\n\t {} \n\n".format(
                    "Naz: Caution; You have activated dry-run, naz may not behave correctly."
                ),
            )

        if not isinstance(client, naz.Client):
            e = ValueError(
                """`client` should be of type:: `naz.Client` You entered: {0}""".format(
                    type(client)
                )
            )
            logger.log(logging.ERROR, {"event": "naz.cli.main", "stage": "end", "error": str(e)})
            sys.exit(77)

        if dry_run:
            return
        # call naz api
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            async_main(client=client, logger=logger, loop=loop, dry_run=dry_run)
        )
    except Exception as e:
        logger.log(logging.ERROR, {"event": "naz.cli.main", "stage": "end", "error": str(e)})
        sys.exit(77)
    finally:
        logger.log(logging.INFO, {"event": "naz.cli.main", "stage": "end"})


async def async_main(
    client: naz.Client,
    logger: naz.log.SimpleLogger,
    loop: asyncio.events.AbstractEventLoop,
    dry_run: bool,
):
    # connect & bind to the SMSC host
    await client.connect()
    await client.tranceiver_bind()

    # send any queued messages to SMSC, read any data from SMSC and continually check the state of the SMSC
    tasks = asyncio.gather(
        client.dequeue_messages(TESTING=dry_run),
        client.receive_data(TESTING=dry_run),
        client.enquire_link(TESTING=dry_run),
        sig._signal_handling(logger=logger, client=client, loop=loop),
        loop=loop,
    )
    await tasks


if __name__ == "__main__":
    main()
