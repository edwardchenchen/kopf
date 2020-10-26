import asyncio

import freezegun
import pytest

from kopf.engines.peering import process_peering_event
from kopf.structs import bodies, primitives


@pytest.mark.parametrize('our_name, our_namespace, their_name, their_namespace', [
    ['our-name', 'our-namespace', 'their-name', 'their-namespace'],
    ['our-name', 'our-namespace', 'their-name', 'our-namespace'],
    ['our-name', 'our-namespace', 'their-name', None],
    ['our-name', 'our-namespace', 'our-name', 'their-namespace'],
    ['our-name', 'our-namespace', 'our-name', None],
    ['our-name', None, 'their-name', 'their-namespace'],
    ['our-name', None, 'their-name', 'our-namespace'],
    ['our-name', None, 'their-name', None],
    ['our-name', None, 'our-name', 'their-namespace'],
    ['our-name', None, 'their-name', 'our-namespace'],
])
async def test_other_peering_objects_are_ignored(
        mocker, settings, our_name, our_namespace, their_name, their_namespace):

    status = mocker.Mock()
    status.items.side_effect = Exception("This should not be called.")
    event = bodies.RawEvent(
        type='ADDED',  # irrelevant
        object={
            'metadata': {'name': their_name, 'namespace': their_namespace},
            'status': status,
        })

    settings.peering.name = our_name
    await process_peering_event(
        raw_event=event,
        freeze_mode=primitives.Toggle(),
        replenished=asyncio.Event(),
        autoclean=False,
        identity='id',
        settings=settings,
        namespace=our_namespace,
    )
    assert not status.items.called


@freezegun.freeze_time('2020-12-31T23:59:59.123456')
async def test_toggled_on_for_higher_priority_peer_when_initially_off(
        caplog, assert_logs, settings):

    event = bodies.RawEvent(
        type='ADDED',  # irrelevant
        object={
            'metadata': {'name': 'name', 'namespace': 'namespace'},  # for matching
            'status': {
                'higher-prio': {
                    'priority': 101,
                    'lifetime': 10,
                    'lastseen': '2020-12-31T23:59:59'
                },
            },
        })
    settings.peering.name = 'name'
    settings.peering.priority = 100

    replenished = asyncio.Event()
    freeze_mode = primitives.Toggle(False)

    caplog.set_level(0)
    assert freeze_mode.is_off()
    await process_peering_event(
        raw_event=event,
        freeze_mode=freeze_mode,
        replenished=replenished,
        autoclean=False,
        namespace='namespace',
        identity='id',
        settings=settings,
    )
    assert freeze_mode.is_on()
    assert_logs(["Freezing operations in favour of"], prohibited=[
        "Possibly conflicting operators",
        "Freezing all operators, including self",
        "Resuming operations after the freeze",
    ])


@freezegun.freeze_time('2020-12-31T23:59:59.123456')
async def test_ignored_for_higher_priority_peer_when_already_on(
        caplog, assert_logs, settings):

    event = bodies.RawEvent(
        type='ADDED',  # irrelevant
        object={
            'metadata': {'name': 'name', 'namespace': 'namespace'},  # for matching
            'status': {
                'higher-prio': {
                    'priority': 101,
                    'lifetime': 10,
                    'lastseen': '2020-12-31T23:59:59'
                },
            },
        })
    settings.peering.name = 'name'
    settings.peering.priority = 100

    replenished = asyncio.Event()
    freeze_mode = primitives.Toggle(True)

    caplog.set_level(0)
    assert freeze_mode.is_on()
    await process_peering_event(
        raw_event=event,
        freeze_mode=freeze_mode,
        replenished=replenished,
        autoclean=False,
        namespace='namespace',
        identity='id',
        settings=settings,
    )
    assert freeze_mode.is_on()
    assert_logs([], prohibited=[
        "Possibly conflicting operators",
        "Freezing all operators, including self",
        "Freezing operations in favour of",
        "Resuming operations after the freeze",
    ])


@freezegun.freeze_time('2020-12-31T23:59:59.123456')
async def test_toggled_off_for_lower_priority_peer_when_initially_on(
        caplog, assert_logs, settings):

    event = bodies.RawEvent(
        type='ADDED',  # irrelevant
        object={
            'metadata': {'name': 'name', 'namespace': 'namespace'},  # for matching
            'status': {
                'higher-prio': {
                    'priority': 99,
                    'lifetime': 10,
                    'lastseen': '2020-12-31T23:59:59'
                },
            },
        })
    settings.peering.name = 'name'
    settings.peering.priority = 100

    replenished = asyncio.Event()
    freeze_mode = primitives.Toggle(True)

    caplog.set_level(0)
    assert freeze_mode.is_on()
    await process_peering_event(
        raw_event=event,
        freeze_mode=freeze_mode,
        replenished=replenished,
        autoclean=False,
        namespace='namespace',
        identity='id',
        settings=settings,
    )
    assert freeze_mode.is_off()
    assert_logs(["Resuming operations after the freeze"], prohibited=[
        "Possibly conflicting operators",
        "Freezing all operators, including self",
        "Freezing operations in favour of",
    ])


@freezegun.freeze_time('2020-12-31T23:59:59.123456')
async def test_ignored_for_lower_priority_peer_when_already_off(
        caplog, assert_logs, settings):

    event = bodies.RawEvent(
        type='ADDED',  # irrelevant
        object={
            'metadata': {'name': 'name', 'namespace': 'namespace'},  # for matching
            'status': {
                'higher-prio': {
                    'priority': 99,
                    'lifetime': 10,
                    'lastseen': '2020-12-31T23:59:59'
                },
            },
        })
    settings.peering.name = 'name'
    settings.peering.priority = 100

    replenished = asyncio.Event()
    freeze_mode = primitives.Toggle(False)

    caplog.set_level(0)
    assert freeze_mode.is_off()
    await process_peering_event(
        raw_event=event,
        freeze_mode=freeze_mode,
        replenished=replenished,
        autoclean=False,
        namespace='namespace',
        identity='id',
        settings=settings,
    )
    assert freeze_mode.is_off()
    assert_logs([], prohibited=[
        "Possibly conflicting operators",
        "Freezing all operators, including self",
        "Freezing operations in favour of",
        "Resuming operations after the freeze",
    ])


@freezegun.freeze_time('2020-12-31T23:59:59.123456')
async def test_toggled_on_for_same_priority_peer_when_initially_off(
        caplog, assert_logs, settings):

    event = bodies.RawEvent(
        type='ADDED',  # irrelevant
        object={
            'metadata': {'name': 'name', 'namespace': 'namespace'},  # for matching
            'status': {
                'higher-prio': {
                    'priority': 100,
                    'lifetime': 10,
                    'lastseen': '2020-12-31T23:59:59'
                },
            },
        })
    settings.peering.name = 'name'
    settings.peering.priority = 100

    replenished = asyncio.Event()
    freeze_mode = primitives.Toggle(False)

    caplog.set_level(0)
    assert freeze_mode.is_off()
    await process_peering_event(
        raw_event=event,
        freeze_mode=freeze_mode,
        replenished=replenished,
        autoclean=False,
        namespace='namespace',
        identity='id',
        settings=settings,
    )
    assert freeze_mode.is_on()
    assert_logs([
        "Possibly conflicting operators",
        "Freezing all operators, including self",
    ], prohibited=[
        "Freezing operations in favour of",
        "Resuming operations after the freeze",
    ])


@freezegun.freeze_time('2020-12-31T23:59:59.123456')
async def test_ignored_for_same_priority_peer_when_already_on(
        caplog, assert_logs, settings):

    event = bodies.RawEvent(
        type='ADDED',  # irrelevant
        object={
            'metadata': {'name': 'name', 'namespace': 'namespace'},  # for matching
            'status': {
                'higher-prio': {
                    'priority': 100,
                    'lifetime': 10,
                    'lastseen': '2020-12-31T23:59:59'
                },
            },
        })
    settings.peering.name = 'name'
    settings.peering.priority = 100

    replenished = asyncio.Event()
    freeze_mode = primitives.Toggle(True)

    caplog.set_level(0)
    assert freeze_mode.is_on()
    await process_peering_event(
        raw_event=event,
        freeze_mode=freeze_mode,
        replenished=replenished,
        autoclean=False,
        namespace='namespace',
        identity='id',
        settings=settings,
    )
    assert freeze_mode.is_on()
    assert_logs([
        "Possibly conflicting operators",
    ], prohibited=[
        "Freezing all operators, including self",
        "Freezing operations in favour of",
        "Resuming operations after the freeze",
    ])
