import { test } from 'node:test';
import assert from 'node:assert/strict';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
const { LocationController, identifyLocation, observeLocationPermission } = await import(pathToFileURL(join(process.env.LOCATION_TEST_BUILD, 'location.js')));
const { selectMapPoint } = await import(pathToFileURL(join(process.env.LOCATION_TEST_BUILD, 'map-location.js')));
const point = { lat: 52.52, lng: 13.405 };
const result = { dataset_status: 'ready', sector: { code: 'soviet', name: 'Soviet' } };
const flush = () => new Promise(resolve => setImmediate(resolve));
function gps() {
  const api = {
    cleared: [], callbacks: [],
    watchPosition(success, failure, options) {
      api.success = success; api.failure = failure; api.options = options;
      api.callbacks.push({ success, failure });
      return api.callbacks.length - 1;
    },
    clearWatch(id) { api.cleared.push(id); },
    position(lat = point.lat, accuracy = 5) { api.success({ coords: { latitude: lat, longitude: point.lng, accuracy } }); },
  };
  return api;
}
function permission(state) {
  const status = new EventTarget();
  status.state = state;
  status.set = state => { status.state = state; status.dispatchEvent(new Event('change')); };
  const permissions = { calls: 0, query: async options => {
    assert.deepEqual(options, { name: 'geolocation' }); permissions.calls++; return status;
  } };
  return { status, permissions };
}

test('API integration sends only identification coordinates, uncached and abortable', async () => {
  const signal = new AbortController().signal;
  let seen;
  assert.deepEqual(await identifyLocation(point, signal, async (url, options) => {
    seen = { url, options }; return { ok: true, json: async () => result };
  }), result);
  assert.equal(seen.url, '/api/v1/sectors/identify?lat=52.52&lng=13.405');
  assert.equal(seen.options.signal, signal);
  assert.equal(seen.options.cache, 'no-store');
});

test('API missing data, outside coverage, errors and malformed results', async () => {
  const signal = new AbortController().signal;
  for (const status of ['missing', 'ready']) {
    const value = { dataset_status: status, sector: null };
    assert.deepEqual(await identifyLocation(point, signal, async () => ({ ok: true, json: async () => value })), value);
  }
  await assert.rejects(identifyLocation(point, signal, async () => ({ ok: false })));
  await assert.rejects(identifyLocation(point, signal, async () => ({ ok: true, json: async () => ({ dataset_status: 'ready', sector: { code: 'invalid' } }) })));
  await assert.rejects(identifyLocation({ lat: NaN, lng: 0 }, signal));
});

test('address selection requests only necessary fields and selects shared coordinates', async () => {
  const calls = [];
  const controller = new LocationController(async p => { calls.push(p); return result; });
  await controller.address({ toPlace: () => ({
    fetchFields: async options => assert.deepEqual(options.fields, ['location', 'formattedAddress']),
    location: { lat: () => point.lat, lng: () => point.lng }, formattedAddress: 'Berlin address',
  }) });
  assert.deepEqual(calls, [point]);
  assert.equal(controller.getSnapshot().source, 'address');
  assert.equal(controller.getSnapshot().label, 'Berlin address');
  assert.equal(controller.getSnapshot().status, 'ready');
});

test('unavailable or out-of-Berlin addresses do not call identification', async () => {
  const controller = new LocationController(async () => { assert.fail('unexpected request'); });
  await controller.address({ toPlace: () => ({ fetchFields: async () => {} }) });
  assert.equal(controller.getSnapshot().status, 'error');
  await controller.address({ toPlace: () => ({ fetchFields: async () => {}, location: { lat: () => 0, lng: () => 0 } }) });
  assert.match(controller.getSnapshot().error, /within Berlin/);
});

test('polygon click stops propagation and selects once; map click uses same workflow', async () => {
  let stopped = false;
  let calls = 0;
  const controller = new LocationController(async () => { calls++; return result; });
  const select = p => controller.manual(p, 'map');
  selectMapPoint({ latLng: { lat: () => point.lat, lng: () => point.lng }, stop: () => { stopped = true; } }, select);
  await flush();
  assert.ok(stopped);
  assert.equal(calls, 1);
  assert.equal(controller.getSnapshot().source, 'map');
  selectMapPoint({ latLng: null }, select);
  assert.equal(calls, 1);
});

test('latest selection wins even when an aborted request resolves late', async () => {
  const pending = [];
  const controller = new LocationController((p, signal) => new Promise(resolve => pending.push({ p, signal, resolve })));
  const first = controller.manual(point, 'map');
  const second = controller.manual({ ...point, lat: 52.6 }, 'map');
  assert.ok(pending[0].signal.aborted);
  pending[1].resolve(result); await second;
  pending[0].resolve({ dataset_status: 'missing', sector: null }); await first;
  assert.deepEqual(controller.getSnapshot().result, result);
  assert.equal(controller.getSnapshot().coordinates.lat, 52.6);
});

test('late place details cannot replace a newer map selection', async () => {
  let resolve;
  const controller = new LocationController(async () => result);
  const address = controller.address({ toPlace: () => ({ fetchFields: () => new Promise(r => { resolve = r; }), location: { lat: () => 52.6, lng: () => 13.4 } }) });
  await controller.manual(point, 'map');
  resolve(); await address;
  assert.equal(controller.getSnapshot().source, 'map');
  assert.deepEqual(controller.getSnapshot().coordinates, point);
});

test('results stay visible until dismissed and dismissal prevents late responses', async () => {
  const controller = new LocationController(async () => result);
  await controller.manual(point, 'map'); await flush();
  assert.equal(controller.getSnapshot().status, 'ready');
  controller.dismiss();
  assert.equal(controller.getSnapshot().status, 'idle');
  assert.equal(controller.getSnapshot().coordinates, undefined);
});

test('request timeout leaves a retryable error', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const controller = new LocationController((_, signal) => new Promise((resolve, reject) => {
    signal.addEventListener('abort', () => reject(new Error('aborted')));
  }));
  const selection = controller.manual(point, 'map');
  t.mock.timers.tick(10000);
  await selection;
  assert.equal(controller.getSnapshot().status, 'error');
  assert.match(controller.getSnapshot().error, /timed out/);
});

test('dismissal invalidates an in-flight response', async () => {
  let resolve;
  const controller = new LocationController(() => new Promise(r => { resolve = r; }));
  const pending = controller.manual(point, 'map');
  controller.dismiss(); resolve(result); await pending;
  assert.equal(controller.getSnapshot().status, 'idle');
  assert.equal(controller.getSnapshot().coordinates, undefined);
});

test('Find me requests a watch only after a click and identifies the user with accuracy', async () => {
  const geo = gps(); const controller = new LocationController(async () => result);
  assert.equal(geo.callbacks.length, 0);
  controller.findMe(geo, true); geo.position(); await flush();
  assert.equal(controller.getSnapshot().following, true);
  assert.equal(controller.getSnapshot().accuracy, 5);
  assert.deepEqual(controller.getSnapshot().user, { ...point, accuracy: 5 });
  assert.equal(geo.options.timeout, 15000);
  controller.deactivate();
});

test('granted permission starts passive location display without centering or identifying', async () => {
  const geo = gps(); const { permissions } = permission('granted');
  const controller = new LocationController(async () => assert.fail('passive GPS must not identify'));
  const cleanup = observeLocationPermission(controller, permissions, geo, true, () => true);
  await flush(); geo.position(); await flush();
  assert.equal(geo.callbacks.length, 1);
  assert.deepEqual(controller.getSnapshot().user, { ...point, accuracy: 5 });
  assert.equal(controller.getSnapshot().following, false);
  assert.equal(controller.getSnapshot().status, 'idle');
  cleanup(); controller.deactivate();
});

test('prompt or denied permission never starts a watcher automatically', async () => {
  for (const state of ['prompt', 'denied']) {
    const geo = gps(); const { permissions } = permission(state);
    const controller = new LocationController();
    const cleanup = observeLocationPermission(controller, permissions, geo, true, () => true);
    await flush(); assert.equal(geo.callbacks.length, 0); cleanup();
  }
});

test('permission changes start one watcher and revocation removes the marker', async () => {
  const geo = gps(); const { status, permissions } = permission('prompt');
  const controller = new LocationController(async () => result);
  const cleanup = observeLocationPermission(controller, permissions, geo, true, () => true);
  await flush(); controller.findMe(geo, true); status.set('granted');
  assert.equal(geo.callbacks.length, 1);
  geo.position(); await flush(); status.set('denied');
  assert.equal(controller.getSnapshot().user, undefined);
  assert.equal(controller.getSnapshot().following, false);
  assert.deepEqual(geo.cleared, [0]);
  geo.position(52.6); assert.equal(controller.getSnapshot().user, undefined);
  cleanup();
});

test('stopping Find me keeps the user marker updating without backend calls', async () => {
  const geo = gps(); let calls = 0;
  const controller = new LocationController(async () => { calls++; return result; });
  controller.findMe(geo, true); geo.position(); await flush();
  controller.stopFollowing(); geo.position(52.6); await flush();
  assert.equal(controller.getSnapshot().following, false);
  assert.equal(controller.getSnapshot().user.lat, 52.6);
  assert.equal(calls, 1);
  assert.deepEqual(geo.cleared, []);
  controller.deactivate(); assert.deepEqual(geo.cleared, [0]);
});

test('manual map selection stops recentering while preserving passive GPS updates', async () => {
  const geo = gps(); let calls = 0;
  const controller = new LocationController(async () => { calls++; return result; });
  controller.findMe(geo, true); geo.position(); await flush();
  await controller.manual(point, 'map'); geo.position(52.6); await flush();
  assert.equal(controller.getSnapshot().source, 'map');
  assert.equal(controller.getSnapshot().following, false);
  assert.equal(controller.getSnapshot().user.lat, 52.6);
  assert.deepEqual(controller.getSnapshot().coordinates, point);
  assert.equal(calls, 2);
  assert.deepEqual(geo.cleared, []);
  controller.deactivate();
});

test('manual address selection remains selected as the user location changes', async () => {
  const geo = gps(); const controller = new LocationController(async () => result);
  controller.findMe(geo, true);
  await controller.address({ toPlace: () => ({ fetchFields: async () => {}, location: { lat: () => point.lat, lng: () => point.lng } }) });
  geo.position(52.6); await flush();
  assert.equal(controller.getSnapshot().source, 'address');
  assert.equal(controller.getSnapshot().following, false);
  assert.deepEqual(controller.getSnapshot().coordinates, point);
  assert.equal(controller.getSnapshot().user.lat, 52.6);
  controller.deactivate();
});

test('permission denial, timeout, unavailable and unsupported locations are separate from sector results', async () => {
  for (const [code, message] of [[1, /denied/], [2, /unavailable/], [3, /timed out/]]) {
    const geo = gps(); const controller = new LocationController(async () => result);
    controller.startTracking(geo, true);
    await controller.manual(point, 'map'); geo.failure({ code });
    assert.match(controller.getSnapshot().locationError, message);
    assert.equal(controller.getSnapshot().following, false);
    assert.deepEqual(controller.getSnapshot().result, result);
    controller.deactivate();
  }
  const controller = new LocationController();
  controller.findMe(undefined, true); assert.match(controller.getSnapshot().locationError, /does not support/);
  controller.findMe(gps(), false); assert.match(controller.getSnapshot().locationError, /HTTPS/);
});

test('repeated positions are accuracy filtered and identification requests are throttled', async () => {
  const geo = gps(); let calls = 0; let now = 0;
  const controller = new LocationController(async () => { calls++; return result; }, () => now);
  controller.findMe(geo, true); geo.position(); await flush();
  now = 20000; geo.position(52.520001); await flush(); assert.equal(calls, 1);
  now = 21000; geo.position(52.521); await flush(); assert.equal(calls, 2);
  now = 22000; geo.position(52.522); await flush(); assert.equal(calls, 2);
  assert.equal(controller.getSnapshot().user.lat, 52.522);
  now = 32000; geo.position(52.523); await flush(); assert.equal(calls, 3);
  controller.deactivate();
});

test('deactivation cleans watcher, cooldown, and stale requests; return resumes passive display only', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const geo = gps(); let resolve; let calls = 0; let now = 0;
  const controller = new LocationController(() => { calls++; return new Promise(r => { resolve = r; }); }, () => now);
  controller.findMe(geo, true); geo.position(); now = 1000; geo.position(52.6);
  const oldCallback = geo.callbacks[0].success;
  controller.deactivate(); resolve(result); await flush();
  assert.deepEqual(geo.cleared, [0]);
  assert.equal(controller.getSnapshot().following, false);
  assert.equal(controller.getSnapshot().status, 'idle');
  const user = controller.getSnapshot().user;
  oldCallback({ coords: { latitude: 52.7, longitude: point.lng, accuracy: 5 } });
  assert.equal(controller.getSnapshot().user, user);
  now = 11000; t.mock.timers.tick(10000); assert.equal(calls, 1);
  const { permissions } = permission('granted');
  const cleanup = observeLocationPermission(controller, permissions, geo, true, () => true);
  await flush(); geo.position(52.61); await flush();
  assert.equal(controller.getSnapshot().user.lat, 52.61);
  assert.equal(controller.getSnapshot().following, false);
  assert.equal(calls, 1);
  cleanup(); controller.deactivate();
});

test('a late permission query after cleanup or hiding cannot start location access', async () => {
  for (const hidden of [true, false]) {
    const geo = gps(); let resolve; const { status } = permission('granted');
    const controller = new LocationController();
    const cleanup = observeLocationPermission(controller, { query: () => new Promise(r => { resolve = r; }) }, geo, true, () => !hidden);
    if (!hidden) cleanup();
    resolve(status); await flush();
    assert.equal(geo.callbacks.length, 0); cleanup();
  }
});

test('permission observer cleanup removes its change listener', async () => {
  const geo = gps(); const { permissions, status } = permission('prompt');
  const controller = new LocationController();
  const cleanup = observeLocationPermission(controller, permissions, geo, true, () => true);
  await flush(); cleanup(); status.set('granted');
  assert.equal(geo.callbacks.length, 0);
});

test('unsupported Permissions API waits for Find me instead of prompting at startup', async () => {
  for (const permissions of [undefined, { query: async () => { throw new Error('not supported'); } }]) {
    const geo = gps(); const controller = new LocationController(async () => result);
    const cleanup = observeLocationPermission(controller, permissions, geo, true, () => true);
    await flush(); assert.equal(geo.callbacks.length, 0);
    controller.findMe(geo, true); geo.position(); await flush();
    assert.equal(controller.getSnapshot().user.lat, point.lat);
    cleanup(); controller.deactivate();
  }
});

test('enabling Find me from passive display reuses the watcher and centers on the existing fix', async () => {
  const geo = gps(); let calls = 0;
  const controller = new LocationController(async () => { calls++; return result; });
  controller.startTracking(geo, true); geo.position();
  controller.findMe(geo, true); await flush();
  assert.equal(geo.callbacks.length, 1);
  assert.equal(controller.getSnapshot().following, true);
  assert.equal(controller.getSnapshot().status, 'ready');
  assert.equal(calls, 1);
  controller.deactivate();
});

test('turning Find me off before the first fix clears loading but keeps passive display active', () => {
  const geo = gps(); const controller = new LocationController();
  controller.findMe(geo, true); controller.stopFollowing();
  assert.equal(controller.getSnapshot().status, 'idle');
  geo.position();
  assert.equal(controller.getSnapshot().user.lat, point.lat);
  assert.equal(controller.getSnapshot().status, 'idle');
  assert.deepEqual(geo.cleared, []);
  controller.deactivate();
});

test('Find me checks the final position after cooldown even if movement stops', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const geo = gps(); let now = 0; let calls = 0;
  const controller = new LocationController(async () => { calls++; return result; }, () => now);
  controller.findMe(geo, true); geo.position(); await flush();
  now = 1000; geo.position(52.522); await flush(); assert.equal(calls, 1);
  now = 10000; t.mock.timers.tick(9000); await flush();
  assert.equal(calls, 2);
  assert.equal(controller.getSnapshot().coordinates.lat, 52.522);
  controller.deactivate();
});

test('stopping Find me cancels a pending identification cooldown', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const geo = gps(); let now = 0; let calls = 0;
  const controller = new LocationController(async () => { calls++; return result; }, () => now);
  controller.findMe(geo, true); geo.position(); await flush();
  now = 1000; geo.position(52.522); controller.stopFollowing();
  now = 10000; t.mock.timers.tick(9000); await flush();
  assert.equal(calls, 1);
  assert.equal(controller.getSnapshot().user.lat, 52.522);
  controller.deactivate();
});

test('GPS accuracy improvements update a stationary marker and accuracy circle state', async () => {
  const geo = gps(); let now = 0;
  const controller = new LocationController(async () => result, () => now);
  controller.findMe(geo, true); geo.position(point.lat, 500); await flush();
  now = 10000; geo.position(point.lat, 5); await flush();
  assert.equal(controller.getSnapshot().user.accuracy, 5);
  assert.equal(controller.getSnapshot().accuracy, 5);
  controller.deactivate();
});

test('a later permission change does not clear the denial error from the GPS callback', async () => {
  const geo = gps(); const { permissions, status } = permission('prompt');
  const controller = new LocationController();
  const cleanup = observeLocationPermission(controller, permissions, geo, true, () => true);
  await flush(); controller.findMe(geo, true); geo.failure({ code: 1 });
  status.set('denied');
  assert.match(controller.getSnapshot().locationError, /denied/);
  cleanup(); controller.deactivate();
});

test('address label falls back to selected suggestion when formatted address is absent or blank', async () => {
  for (const formattedAddress of [undefined, null, '   ']) {
    const controller = new LocationController(async () => result);
    await controller.address({
      text: { text: 'Alexanderplatz, Berlin, Germany' },
      toPlace: () => ({ fetchFields: async () => {}, formattedAddress,
        location: { lat: () => point.lat, lng: () => point.lng } }),
    });
    assert.equal(controller.getSnapshot().label, 'Alexanderplatz, Berlin, Germany');
  }
});

test('address label includes the selected place name when Google omits it without duplicating street addresses', async () => {
  for (const [name, formattedAddress, expected] of [
    ['Alexanderplatz', 'Mitte, 10178 Berlin, Germany', 'Alexanderplatz, Mitte, 10178 Berlin, Germany'],
    ['Friedrichstraße 42', 'Friedrichstraße 42, 10969 Berlin, Germany', 'Friedrichstraße 42, 10969 Berlin, Germany'],
  ]) {
    const controller = new LocationController(async () => result);
    await controller.address({ mainText: { text: name }, toPlace: () => ({
      fetchFields: async () => {}, formattedAddress,
      location: { lat: () => point.lat, lng: () => point.lng },
    }) });
    assert.equal(controller.getSnapshot().label, expected);
  }
});

test('dismissing a selected address clears its marker state and preserves the live user location', async () => {
  const geo = gps();
  const controller = new LocationController(async () => result);
  controller.startTracking(geo, true); geo.position();
  await controller.manual({ lat: 52.6, lng: 13.4 }, 'address', 'Selected address');
  controller.dismiss();
  assert.equal(controller.getSnapshot().coordinates, undefined);
  assert.equal(controller.getSnapshot().source, undefined);
  assert.equal(controller.getSnapshot().label, undefined);
  assert.equal(controller.getSnapshot().accuracy, undefined);
  assert.deepEqual(controller.getSnapshot().user, { ...point, accuracy: 5 });
  assert.deepEqual(geo.cleared, []);
  controller.deactivate();
});

test('Find me rejects an outside first fix before recentering or requesting identification', async () => {
  const geo = gps();
  const controller = new LocationController(async () => assert.fail('outside coordinates must not identify'));
  const snapshots = [];
  const unsubscribe = controller.subscribe(() => snapshots.push(controller.getSnapshot()));
  controller.findMe(geo, true); geo.position(53.55); await flush();
  assert.equal(controller.getSnapshot().following, false);
  assert.match(controller.getSnapshot().locationError, /outside Berlin/);
  assert.equal(controller.getSnapshot().status, 'idle');
  assert.equal(controller.getSnapshot().coordinates, undefined);
  assert.equal(controller.getSnapshot().user.lat, 53.55);
  assert.ok(!snapshots.some(state => state.following && state.user?.lat === 53.55));
  unsubscribe(); controller.deactivate();
});

test('Find me with a known outside location preserves the current map selection', async () => {
  const geo = gps(); let calls = 0;
  const controller = new LocationController(async () => { calls++; return result; });
  controller.startTracking(geo, true); geo.position(53.55);
  await controller.manual(point, 'map');
  controller.findMe(geo, true); await flush();
  assert.equal(controller.getSnapshot().following, false);
  assert.match(controller.getSnapshot().locationError, /outside Berlin/);
  assert.deepEqual(controller.getSnapshot().coordinates, point);
  assert.deepEqual(controller.getSnapshot().result, result);
  assert.equal(calls, 1);
  geo.position(53.551); assert.match(controller.getSnapshot().locationError, /outside Berlin/);
  controller.deactivate();
});

test('passive outside fixes do not show an error until Find me is clicked', () => {
  const geo = gps(); const controller = new LocationController();
  controller.startTracking(geo, true); geo.position(53.55);
  assert.equal(controller.getSnapshot().locationError, undefined);
  assert.equal(controller.getSnapshot().following, false);
  controller.deactivate();
});

test('crossing the Berlin bounds stops Find me, cancels cooldown, and ignores a stale sector response', async t => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  const geo = gps(); let resolve; let calls = 0; let now = 0;
  const controller = new LocationController(() => { calls++; return new Promise(r => { resolve = r; }); }, () => now);
  controller.findMe(geo, true); geo.position();
  now = 1000; geo.position(52.6);
  geo.position(53.55);
  assert.equal(controller.getSnapshot().following, false);
  assert.match(controller.getSnapshot().locationError, /outside Berlin/);
  resolve(result); await flush();
  now = 11000; t.mock.timers.tick(10000); await flush();
  assert.equal(calls, 1);
  assert.equal(controller.getSnapshot().status, 'idle');
  assert.equal(controller.getSnapshot().result, undefined);
  controller.deactivate();
});

test('a small GPS movement across the boundary cannot bypass the Berlin check', async () => {
  const geo = gps(); const controller = new LocationController(async () => result);
  controller.findMe(geo, true); geo.position(52.67999); await flush();
  geo.position(52.68001); await flush();
  assert.equal(controller.getSnapshot().following, false);
  assert.equal(controller.getSnapshot().user.lat, 52.68001);
  assert.match(controller.getSnapshot().locationError, /outside Berlin/);
  controller.deactivate();
});

test('returning inside Berlin updates the marker but requires a new Find me click to recenter', async () => {
  const geo = gps(); let calls = 0;
  const controller = new LocationController(async () => { calls++; return result; });
  controller.findMe(geo, true); geo.position(53.55); await flush();
  geo.position(); await flush();
  assert.equal(controller.getSnapshot().following, false);
  assert.equal(controller.getSnapshot().locationError, undefined);
  assert.equal(calls, 0);
  controller.findMe(geo, true); await flush();
  assert.equal(controller.getSnapshot().following, true);
  assert.equal(calls, 1);
  controller.deactivate();
});
