#! /usr/bin/env python
import bernhard
from optparse import OptionParser
import os.path
import socket
import subprocess
import sys
import time

def separate_from_commas(comma_str):
    """
    Takes a string of comma separated elements
    and returns an array of those elements as Strings.
    """
    if comma_str:
        return comma_str.split(",")
    else:
        return []

def parse_states(states_str):
    """
    Parses a string of state information for interpreting return codes.
    E.g. "ok:0,1|warn:2,3" => {0: "ok", 1: "ok", 2: "warn", 3: "warn"}
    """
    states = {}
    for state_info in states_str.split("|"):
        name, codes = state_info.split(":")
        for code in separate_from_commas(codes):
            states[int(code)] = name
    return states

def run_state(proc, state_table):
    """
    Returns the name of the state that matches the return code of proc.
    Assumes proc has already executed. See parse_states.
    """
    return state_table.get(proc.returncode, "error")

def run_command(command_str):
    proc = subprocess.Popen(command_str, stdout=subprocess.PIPE, shell=True)
    proc.wait()
    return proc

def command_name(command_array):
    command = command_array[0]
    return os.path.basename(command)


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("--riemann-host", default="localhost", help="The address of Riemann")
    parser.add_option("--riemann-port", default=5555, help="The port Riemann is running on")
    parser.add_option("--tags", default=None, help="Optional tags for the event")
    parser.add_option("--ttl", default=None, help="An optional TTL for the event")
    parser.add_option("--states", default="ok:0", help="Describes a mapping of return codes and event states.  e.g. ok:0,1|warn:2,3. Return codes without an explicit mapping are assumed error. default=ok:0")

    options, command = parser.parse_args()
    if not command:
        print "Fatal: no command given"
        parser.print_help()
        exit(-1)

    command_str = ' '.join(command)
    start = time.time()
    proc = run_command(command_str)
    end = time.time()
    duration = end - start

    state_table = parse_states(options.states)
    riemann = bernhard.Client(host=options.riemann_host, port=options.riemann_port, transport=bernhard.UDPTransport)
    riemann_event = {}
    riemann_event["service"] = command_name(command)
    riemann_event["state"]  = run_state(proc, state_table)
    riemann_event["description"] = proc.stdout.read()
    if options.ttl:
        riemann_event["ttl"] = int(options.ttl)
    riemann_event["host"]  = socket.gethostname()
    riemann_event["metric"] = duration
    riemann_event["tags"] = separate_from_commas(options.tags)
    riemann_event["attributes"] = {}
    riemann_event["attributes"]["return_code"] = proc.returncode
    riemann_event["attributes"]["command"] = command_str

    print riemann_event

    riemann.send(riemann_event)
    exit(proc.returncode)