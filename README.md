# Lawo Device Factory

The LDF package has been developed collaboratively by QA Engineers across the Lawo product lines. It is used at the core of all automated test cases executed by the AuLait Framework which enables automated testing across the entire Lawo product line.

In short, the package works by creating an object for any real world Lawo endpoint, and utilises the native HOME messaging system (NATS) as well as other protocol (Ember+, Systemlink) to monitor, control and configure any device in the ecosystem as well as perform actions at the HOME system level.

## Installation Options

There are multiple options for deploying LDF functionality:

### PyPi Package

A pip installable python package is available:

    pip install --extra-index-url https://ccp-tea.lawo.de/api/packages/quality-assurance/pypi/simple/ lawo-device-factory

### Docker Container

Lightweight Linux container image providing a Python environment with LDF pre-installed

    docker pull ccp-tea.lawo.de/quality-assurance/lawo-device-factory:latest
---

## Getting Started

| Topic                                                         | Description                                           |
| ------------------------------------------------------------- | -------------------------------------------           |
| [API Reference](docs/wiki/api_doc_generation.md)              | Complete API documentation  - TODO: Requires Hosting! |
| [Code Examples](docs/wiki/examples/example_index.md)          | Examples of various LDF use cases                     |

---

## Development & Roadmap

| Topic                                                                      | Description                                                                  |
| -------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| [2026 Roadmap](docs/wiki/roadmaps/2026_roadmap.md)                         | Overview of intended developments for 2026                                   |
| [PSG Use Cases](docs/wiki/roadmaps/psg_use_cases.md)                       | Professional Services Group requirements and features                        |
| [Contributing](docs/wiki/legal/contributions.md)                           | Guidelines for contributing to LDF and AuLait                                |
| [Changelog](CHANGELOG.md)                                                  | Version history and release notes                                            |
| [External Usage Guidelines](docs/wiki/legal/external_usage_agreement.md)   | Guidelines and considerations when deploying LDF created tools outside of QA |

---

## Reference

| Topic                                                                          | Description                           |
| ------------------------------------------------------------------------------ | ------------------------------------- |
| [Issues](https://ccp-tea.lawo.de/quality-assurance/lawo-device-factory/issues) | Issue tracker for Lawo Device Factory |

---

## AuLait Framework

The LDF package is part of the AuLait Framework for developing automated test cases for any Lawo product line. For more information on the other components of the framework, see the links below:

| Topic                                                                                     | Description                                      |
| ----------------------------------------------------------------------------------------- | ------------------------------------------------ |
| [Test Runner](https://ccp-tea.lawo.de/quality-assurance/aulait-test-runner)               | Flask-based web application for pytest execution |
| [POM Library](https://ccp-tea.lawo.de/quality-assurance/aulait-pom-library)               | Page Object Model library for UI automation      |
| [Halo Observability](https://ccp-tea.lawo.de/quality-assurance/aulait-test-halo)          | Compatibility matrix and observability tooling   |
| [Blueprint Test Suite](https://ccp-tea.lawo.de/quality-assurance/test-suite-blueprints)   | End-to-end system testing                        |
