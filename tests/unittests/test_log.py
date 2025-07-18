# This file is part of cloud-init. See LICENSE file for license information.

"""Tests for cloudinit.log"""

import datetime
import io
import logging
import time
from typing import cast

import pytest

from cloudinit import lifecycle, util
from cloudinit.analyze.dump import CLOUD_INIT_ASCTIME_FMT
from cloudinit.log import loggers


@pytest.fixture
def ci_logs():
    return io.StringIO()


@pytest.fixture
def log(ci_logs):
    # set up a logger like cloud-init does in setup_logging, but instead
    # of sys.stderr, we'll plug in a StringIO() object so we can see
    # what gets logged
    logging.Formatter.converter = time.gmtime
    ci_root = logging.getLogger()
    console = logging.StreamHandler(ci_logs)
    console.setFormatter(logging.Formatter(loggers.DEFAULT_LOG_FORMAT))
    console.setLevel(logging.DEBUG)
    ci_root.addHandler(console)
    ci_root.setLevel(logging.DEBUG)
    LOG = logging.getLogger("test_cloudinit_logger")
    return LOG


class TestCloudInitLogger:

    def test_logger_uses_gmtime(self, log, ci_logs):
        """Test that log message have timestamp in UTC (gmtime)"""

        # Log a message, extract the timestamp from the log entry
        # convert to datetime, and compare to a utc timestamp before
        # and after the logged message.

        # Due to loss of precision in the LOG timestamp, subtract and add
        # time to the utc stamps for comparison
        #
        # utc_before: 2017-08-23 14:19:42.569299
        # parsed dt : 2017-08-23 14:19:43.069000
        # utc_after : 2017-08-23 14:19:43.570064

        def remove_tz(_dt: datetime.datetime) -> datetime.datetime:
            """
            Removes the timezone object from an aware datetime dt without
            conversion of date and time data
            """
            return _dt.replace(tzinfo=None)

        utc_before = remove_tz(
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(0, 0.5)
        )
        log.error("Test message")
        utc_after = remove_tz(
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(0, 0.5)
        )

        # extract timestamp from log:
        # 2017-08-23 14:19:43,069 - test_log.py[ERROR]: Test message
        logstr = ci_logs.getvalue().splitlines()[0]
        timestampstr = logstr.split(" - ")[0]
        parsed_dt = datetime.datetime.strptime(
            timestampstr, CLOUD_INIT_ASCTIME_FMT
        )

        assert utc_before < parsed_dt
        assert parsed_dt < utc_after
        assert utc_before < utc_after
        assert utc_after > parsed_dt


class TestDeprecatedLogs:
    def test_deprecated_log_level(self, caplog):
        logger = cast(loggers.CustomLoggerType, logging.getLogger())
        logger.deprecated("deprecated message")
        assert "DEPRECATED" == caplog.records[0].levelname
        assert "deprecated message" in caplog.text

    def test_trace_log_level(self, caplog):
        logger = cast(loggers.CustomLoggerType, logging.getLogger())
        logger.setLevel(logging.NOTSET)
        logger.trace("trace message")
        assert "TRACE" == caplog.records[0].levelname
        assert "trace message" in caplog.text

    @pytest.mark.parametrize(
        "expected_log_level, deprecation_info_boundary",
        (
            pytest.param(
                "DEPRECATED",
                "19.2",
                id="test_same_deprecation_info_boundary_is_deprecated_level",
            ),
            pytest.param(
                "INFO",
                "19.1",
                id="test_lower_deprecation_info_boundary_is_info_level",
            ),
        ),
    )
    def test_deprecate_log_level_based_on_features(
        self,
        expected_log_level,
        deprecation_info_boundary,
        caplog,
        mocker,
        clear_deprecation_log,
    ):
        """Deprecation log level depends on key deprecation_version

        When DEPRECATION_INFO_BOUNDARY is set to a version number, and a key
        has a deprecated_version with a version greater than the boundary
        the log level is INFO instead of DEPRECATED. If
        DEPRECATION_INFO_BOUNDARY is set to the default, "devel", all
        deprecated keys are logged at level DEPRECATED.
        """
        mocker.patch.object(
            util.features,
            "DEPRECATION_INFO_BOUNDARY",
            deprecation_info_boundary,
        )
        lifecycle.deprecate(
            deprecated="some key",
            deprecated_version="19.2",
            extra_message="dont use it",
        )
        assert expected_log_level == caplog.records[0].levelname
        assert (
            "some key is deprecated in 19.2 and scheduled to be removed in"
            " 24.2" in caplog.text
        )

    def test_log_deduplication(self, caplog):
        loggers.define_extra_loggers()
        lifecycle.deprecate(
            deprecated="stuff",
            deprecated_version="19.1",
            extra_message=":)",
        )
        lifecycle.deprecate(
            deprecated="stuff",
            deprecated_version="19.1",
            extra_message=":)",
        )
        lifecycle.deprecate(
            deprecated="stuff",
            deprecated_version="19.1",
            extra_message=":)",
            schedule=6,
        )
        assert 2 == len(caplog.records)


def test_logger_prints_to_stderr(capsys):
    message = "to stdout"
    loggers.setup_basic_logging()
    logging.getLogger().warning(message)
    assert message in capsys.readouterr().err
