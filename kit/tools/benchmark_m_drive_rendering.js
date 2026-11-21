'use strict';

const assert = require('assert');
const fs = require('fs');
const net = require('net');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');
const { headUnit } = require('./hu-stub');

const ROOT = path.resolve(__dirname, '../..');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'm-drive-fps-'));
const stage = path.join(tmp, 'm_drive');
const socket = path.join(tmp, 'render.sock');
const outAt = process.argv.indexOf('--out');
const output = outAt >= 0 ? path.resolve(process.argv[outAt + 1]) : null;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const clock = () => { const t = process.hrtime(); return t[0] * 1000 + t[1] / 1e6; };

function remove(dir) {
    fs.readdirSync(dir).forEach((name) => {
        const file = path.join(dir, name);
        if (fs.lstatSync(file).isDirectory()) remove(file);
        else fs.unlinkSync(file);
    });
    fs.rmdirSync(dir);
}
process.on('exit', () => remove(tmp));

function message(type, payload) {
    const data = Buffer.alloc(8 + payload.length);
    data.writeUInt32LE(type, 0);
    data.writeUInt32LE(payload.length, 4);
    payload.copy(data, 8);
    return data;
}
const words = (...data) => Buffer.from(new Uint32Array(data).buffer);
const frames = [], images = [], renderTimes = [], logs = [], peers = new Set();
const server = net.createServer((peer) => {
    peers.add(peer);
    let buffer = Buffer.alloc(0), timer = null, lastTick = 0;
    peer.on('error', () => {});
    peer.on('close', () => { peers.delete(peer); if (timer) clearTimeout(timer); });
    peer.on('data', (data) => {
        buffer = Buffer.concat([buffer, data]);
        while (buffer.length >= 8) {
            const type = buffer.readUInt32LE(0), size = buffer.readUInt32LE(4);
            if (buffer.length < 8 + size) break;
            buffer = buffer.slice(8 + size);
            if (type === 1) {
                peer.write(message(0x4d520101, words(1, 1, 7)));
                peer.write(message(101, words(4, 1920, 720, 1)));
            }
            if (type === 7) {
                frames.push(clock());
                if (!timer) timer = setTimeout(() => {
                    timer = null;
                    lastTick = clock();
                    if (!peer.destroyed) peer.write(message(102, words(frames.length, 0)));
                }, Math.max(0, lastTick + 1000 / 60 - clock()));
            }
        }
    });
});

async function until(label, fn, timeout) {
    const end = clock() + (timeout || 4000);
    while (!fn()) {
        if (clock() > end) throw new Error('Timed out: ' + label);
        await sleep(20);
    }
}

async function sample(name, seconds) {
    await sleep(400);
    const start = clock(), f0 = frames.length, i0 = images.length, t0 = renderTimes.length;
    await sleep(seconds * 1000);
    const elapsed = clock() - start, times = renderTimes.slice(t0);
    const result = {
        name, seconds: Number((elapsed / 1000).toFixed(3)),
        commandFrames: frames.length - f0, softwareImages: images.length - i0,
        commandFps: Number(((frames.length - f0) * 1000 / elapsed).toFixed(1)),
        softwareFps: Number(((images.length - i0) * 1000 / elapsed).toFixed(1)),
        appDrawMs: times.length ? Number((times.reduce((a, b) => a + b, 0) / times.length).toFixed(3)) : null,
    };
    console.log(JSON.stringify(result));
    return result;
}

(async () => {
    const built = spawnSync('python3', ['-c', 'import sys;sys.path.insert(0,sys.argv[1]);import build;build.DIST=sys.argv[2];build.build("m_drive",preview_only=True)',
        path.join(ROOT, 'kit/tools'), tmp], { encoding: 'utf8' });
    assert.strictEqual(built.status, 0, built.stderr || built.stdout);
    console.log('Staged native app. Measuring host command delivery with a 60 Hz compositor stand-in, not physical GPU performance.');
    delete process.env.MGU_RENDERER;
    delete process.env.MGU_RENDERD_FILE;
    process.env.MGU_RENDERD_SOCKET = socket;
    await new Promise((r) => server.listen(socket, r));
    const subs = {};
    const signals = {
        watch: async (iface, instance, handlers) => { subs[iface] = handlers; return { available: true }; },
        proxy: async () => { throw new Error('Benchmark has no vehicle diagnostic connection'); },
    };
    const data = path.join(tmp, 'data');
    fs.mkdirSync(data);
    const log = { info: (s) => logs.push(s), warn: (s) => logs.push(s), error: (s) => logs.push(s), debug() {} };
    const hu = headUnit(stage, { live: true, dataDir: data, log,
        sets: { demo: 'off', controls: 'off', renderer: 'auto' },
        image: () => { images.push(clock()); return Promise.resolve(); } });
    hu.ctx.signals = signals;
    const ui = require(path.join(stage, 'source/javascript/ui'));
    const draw = ui.draw;
    ui.draw = function () { const start = clock(); const value = draw.apply(this, arguments); renderTimes.push(clock() - start); return value; };
    let idle = false;
    const feed = setInterval(() => {
        const h = subs['de.bmw.infotainment.vehicle.CDS'];
        if (h) {
            h.statusEngineSpeed2({ actualValueRPMEngineCrankshaft: Math.round((idle ? 900 : 3200 + 2200 * Math.sin(clock() / 600)) * 4) });
            h.statusEngineTemperature({ temperatureEngineDrive: 138, temperatureEngineOilDrive: 150 });
        }
    }, 50);
    hu.start();
    await until('native renderer active', () => hu.display.active('MAIN'));
    await sleep(700);
    const results = [];
    results.push(await sample('automatic_native_moving', 2));
    assert(results[0].commandFps >= 45 && results[0].commandFps <= 80, 'Native command delivery must follow compositor ticks, not the 10 fps software timer.');
    hu.settings.set('renderer', 'software');
    await until('software selected', () => !hu.display.active('MAIN'));
    const software = await sample('selected_software_moving', 2);
    results.push(software);
    assert(software.softwareFps > 0 && software.softwareFps <= 15 && software.commandFrames === 0);
    await new Promise((r) => server.close(r));
    hu.settings.set('renderer', 'auto');
    const missing = await sample('automatic_renderer_missing', 1);
    results.push(missing);
    assert(missing.softwareImages > 0 && missing.commandFrames === 0);
    await new Promise((r) => server.listen(socket, r));
    await until('automatic hardware-path recovery', () => hu.display.active('MAIN'), 6500);
    const restored = await sample('automatic_native_restored', 2);
    results.push(restored);
    assert(restored.commandFps >= 45 && restored.softwareImages === 0);
    idle = true;
    await sleep(1600);
    const still = await sample('automatic_native_static', 2);
    results.push(still);
    assert(still.commandFrames <= 4, 'A static page should retain unchanged-frame suppression.');
    clearInterval(feed);
    hu.ui.home();
    peers.forEach((p) => p.destroy());
    await new Promise((r) => server.close(r));
    const report = { environment: 'Host native-runtime protocol test with a 60 Hz compositor stand-in. No physical GPU or vehicle measurement.', results };
    if (output) fs.writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
    console.log('PASS: automatic native path, software fallback, renderer recovery, and idle-frame suppression.');
    process.exit(0);
})().catch((e) => { console.error(e.stack, logs.slice(-10)); process.exit(1); });
