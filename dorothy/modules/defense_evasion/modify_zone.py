#
# Licensed to Elasticsearch under one or more contributor
# license agreements. See the NOTICE file distributed with
# this work for additional information regarding copyright
# ownership. Elasticsearch licenses this file to you under
# the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#

# Make a temporary modification to an Okta network zone

import logging.config
import time

import click

from dorothy.core import (
    print_module_info,
    set_module_options,
    reset_module_options,
    check_module_options,
    get_zone_object,
    index_event,
)
from dorothy.modules.defense_evasion.defense_evasion import defense_evasion

LOGGER = logging.getLogger(__name__)
MODULE_DESCRIPTION = "Make a temporary change to an Okta network zone"
TACTICS = ["Defense Evasion", "Impact"]
URL_OR_API_TOKEN_ERROR = "ERROR. Verify that the Okta URL and API token in your configuration profile are correct"

MODULE_OPTIONS = {"id": {"value": None, "required": True, "help": "The unique ID for the network zone"}}


@defense_evasion.subshell(name="modify-zone")
@click.pass_context
def modify_zone(ctx):
    """Make a temporary change to an Okta network zone.

    This module renames the specified network zone and then reverts the change. This basic operation is enough for
    defenders to test their ability to monitor for and detect unexpected changes to Okta network zones."""


@modify_zone.command()
def info():
    """Show available options and their current values for this module"""

    print_module_info(MODULE_OPTIONS)


@modify_zone.command()
@click.pass_context
@click.option("--id", help=MODULE_OPTIONS["id"]["help"])
def set(ctx, **kwargs):
    """Set one or more options for this module"""

    if all(value is None for value in kwargs.values()):
        return click.echo(ctx.get_help())

    else:
        global MODULE_OPTIONS
        MODULE_OPTIONS = set_module_options(MODULE_OPTIONS, kwargs)


@modify_zone.command()
def reset():
    """Reset the options for this module"""

    global MODULE_OPTIONS
    MODULE_OPTIONS = reset_module_options(MODULE_OPTIONS)


@modify_zone.command()
@click.pass_context
def execute(ctx):
    """Execute this module with the configured options"""

    error = check_module_options(MODULE_OPTIONS)

    if error:
        return

    zone_id = MODULE_OPTIONS["id"]["value"]

    zone = get_zone_object(ctx, zone_id)

    if zone:
        original_name = zone["name"]
        new_name = f'{zone["name"]} TEMP_STRING'

        # Rename the zone
        rename_zone(ctx, zone, original_name, new_name)
        # Change the policy name back to its original value
        rename_zone(ctx, zone, new_name, original_name)

        return


def rename_zone(ctx, zone, original_name, new_name):
    """Update an existing network zone with a new name"""

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"SSWS {ctx.obj.api_token}",
    }

    params = {}
    # Values for "type" and "name" and "gateways" OR "proxies are required when updating a network zone object
    payload = {"type": zone["type"], "name": new_name, "gateways": zone.get("gateways"), "proxies": zone.get("proxies")}

    url = f'{ctx.obj.base_url}/zones/{zone["id"]}'

    try:
        msg = f'Attempting to rename network zone "{original_name}" ({zone["id"]}) to "{new_name}"'
        LOGGER.info(msg)
        index_event(ctx.obj.es, module=__name__, event_type="INFO", event=msg)
        click.echo(f"[*] {msg}")
        response = ctx.obj.session.put(url, headers=headers, params=params, json=payload, timeout=7)
    except Exception as e:
        LOGGER.error(e, exc_info=True)
        index_event(ctx.obj.es, module=__name__, event_type="ERROR", event=e)
        click.secho(f"[!] {URL_OR_API_TOKEN_ERROR}", fg="red")
        response = None

    if response.ok:
        msg = f'Network zone "{original_name}" ({zone["id"]}) changed to "{new_name}"'
        LOGGER.info(msg)
        index_event(ctx.obj.es, module=__name__, event_type="INFO", event=msg)
        click.secho(f"[*] {msg}", fg="green")
        get_zone_object(ctx, zone["id"])
        time.sleep(1)

    else:
        msg = (
            f'Error modifying network zone {zone["id"]}\n'
            f"    Response Code: {response.status_code} | Response Reason: {response.reason}\n"
            f'    Error Code: {response.json().get("errorCode")} | Error Summary: {response.json().get("errorSummary")}'
        )
        LOGGER.error(msg)
        index_event(ctx.obj.es, module=__name__, event_type="ERROR", event=msg)
        click.secho(f"[!] {msg}", fg="red")
