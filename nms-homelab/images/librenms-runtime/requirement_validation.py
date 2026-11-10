#!/usr/bin/env python3
"""Validate LibreNMS requirements without the removed pkg_resources API.

Inputs are PEP 508 requirement strings and installed distribution metadata.
The caller owns output verbosity. Return 0 for satisfied requirements, 1 for a
missing distribution, 2 for a version conflict, and 4 for malformed metadata.
Dependencies and requested extras are checked recursively; a visited set prevents
cycles. The image explicitly installs the public packaging parser.
"""
from importlib import metadata
from packaging.requirements import InvalidRequirement, Requirement


def check(requirements, verbose=False):
    pending = list(requirements)
    visited = set()
    while pending:
        text = pending.pop()
        try:
            requirement = Requirement(text)
            if requirement.marker and not requirement.marker.evaluate():
                continue
            key = (requirement.name.lower().replace("_", "-"),
                   str(requirement.specifier), tuple(sorted(requirement.extras)))
            if key in visited:
                continue
            visited.add(key)
            distribution = metadata.distribution(requirement.name)
            if requirement.specifier and not requirement.specifier.contains(
                    distribution.version, prereleases=True):
                if verbose:
                    print(f"Required version not satisfied: {text}; installed {distribution.version}")
                return 2
            for dependency_text in distribution.requires or []:
                dependency = Requirement(dependency_text)
                extras = requirement.extras or {""}
                if dependency.marker and not any(
                        dependency.marker.evaluate({"extra": extra}) for extra in extras):
                    continue
                # Its parent extras have already selected this dependency.
                dependency.marker = None
                pending.append(str(dependency))
        except metadata.PackageNotFoundError:
            if verbose:
                print(f"Package not found: {text}")
            return 1
        except (InvalidRequirement, ValueError) as error:
            if verbose:
                print(f"Invalid requirement metadata: {error}")
            return 4
    return 0
