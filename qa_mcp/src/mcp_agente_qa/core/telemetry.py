"""
# Telemetry Module

## Description
This module initializes telemetry for the botframework application using Azure Application Insights. It configures
logging and tracing to monitor application performance and behavior.

## Version Notes
- Version: 0.0.1
- Author: sergio.vargas@bigview.com.co
- Date: 2023-10-05
- Initial implementation of telemetry integration.

## Usage
- Ensure the `APPINSIGHTS_INSTRUMENTATION_KEY` environment variable is set.
- Logs and traces are sent to Azure Application Insights if the key is provided.
- If the key is missing, telemetry is partially disabled.

## Example
```python
from core.storage.telemetry import logger, tracer
logger.info("Application started")
tracer.span(name="example_span")
```
"""

import logging
import sys
from .enviroment.enviroments import get_environment_variables
from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace.tracer import Tracer
from opencensus.trace.samplers import ProbabilitySampler


env = get_environment_variables()  # Retrieve environment variables using the get_environment_variables function.

# Initialize the logger for the botframework application.

logger = logging.getLogger(env.APP_NAME)
logger.setLevel(env.LOGLEVEL)  # Set the logging level to INFO. 
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('[%(asctime)s][%(name)s][%(levelname)s][%(filename)s:%(lineno)d]: %(message)s'))
# Create a console handler for logging to the console.
logger.addHandler(handler)

# Retrieve the Application Insights instrumentation key from environment variables.
try:
    APPINSIGHTS_KEY = env.APPINSIGHTS_KEY
except Exception as e:
    logger.warning(f"⚠️ Failed to retrieve APPINSIGHTS_KEY: {e}")
    APPINSIGHTS_KEY = None

# Check if the Application Insights instrumentation key is available.
if APPINSIGHTS_KEY:
    try:
        # Add the AzureLogHandler to the logger for sending logs to Application Insights.
        handler = AzureLogHandler(connection_string=f'InstrumentationKey={APPINSIGHTS_KEY}')
        handler.setFormatter(logging.Formatter('[%(asctime)s][%(name)s][%(levelname)s][%(filename)s:%(lineno)d]: %(message)s'))
        # Create a console handler for logging to streaming.
        logger.addHandler(handler)

        # Initialize the tracer for Application Insights telemetry.
        tracer = Tracer(
            exporter=AzureExporter(connection_string=f'InstrumentationKey={APPINSIGHTS_KEY}'),  # Set the exporter.
            sampler=ProbabilitySampler(1.0)  # Use a probability sampler with 100% sampling.
        )

        # Log a message indicating that Application Insights has been initialized.
        logger.info("✅ Application Insights initialized")
    except Exception as e:
        logger.error(f"⚠️ Failed to initialize Application Insights: {e}")
        tracer = Tracer()
else:
    # Fallback tracer when the instrumentation key is missing.
    tracer = Tracer()

    # Log a warning indicating that telemetry is not fully enabled.
    logger.warning("⚠️ APPINSIGHTS_INSTRUMENTATION_KEY is missing. Telemetry is not fully enabled.")


def progress_bar(current: int, total: int, bar_length: int = 40) -> None:
    """
    Displays a progress bar in the console.

    Args:
        current (int): The current progress value.
        total (int): The total value for completion.
        bar_length (int, optional): The length of the progress bar. Defaults to 40.
    """
    fraction = current / total
    filled_length = int(bar_length * fraction)
    bar = '█' * filled_length + '-' * (bar_length - filled_length)
    percent = fraction * 100
    sys.stdout.write(f'\r|{bar}| {percent:.2f}% Complete')
    sys.stdout.flush()
    if current == total:
        sys.stdout.write('\n')


def log_header(message: str) -> None:
    """
    Logs a formatted header message.

    Args:
        message (str): The message to be logged as a header.
    """
    logger.info("================================================================")
    logger.info(f"| {message}")
    logger.info("================================================================")
