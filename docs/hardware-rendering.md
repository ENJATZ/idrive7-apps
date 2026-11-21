# Run M Drive with the native GPU renderer

M Drive already uses the hardware rendering path when it is available. **Renderer > Automatic** is
the default. The runtime connects to `mgu-renderd` or the MGU Store's compatible `mgu-render` service,
sends drawing commands, and lets the native OpenGL ES 2 renderer draw the dashboard on a Wayland
compositor layer. It avoids the normal per-frame PNG route through the BMW HMI.

The upstream [renderer documentation](https://github.com/cauliflowermossgrape/idrive7-apps/blob/main/kit/renderd/README.md)
describes the display-paced GPU path and software fallback. The
[renderer project's documentation](https://github.com/robertnisipeanu/mgu-store/blob/main/native/mgu-render/README.md)
describes its EGL, OpenGL ES, layer placement, sockets, and performance diagnostics.

## Frame rates

The native path aims for the display's refresh rate, normally up to 60 FPS. The `10` in
`ctx.loop('MAIN', 10, render)` limits the software fallback only. Native frames follow compositor
callbacks. Raising that number would increase fallback CPU work without increasing native FPS.

The dashboard intentionally sends identical frames only once a second. This keeps an idle screen
cheap to draw. Moving bars and gauge arcs still animate at the native frame rate. RPM digits are
held for 200 milliseconds to keep the number readable. Vehicle signal notifications and diagnostic
polling have separate rates; faster drawing does not require more ECU traffic.

## Install and select the native renderer

M Drive declares dependencies on `idrive7-renderd` 2.1.18 and `mgu-inputgate` 1.1.0. The renderer
source and matching prebuilt head-unit binary are already included. An SDK-equipped build can
package them with the app:

```sh
python3 kit/tools/make_kit.py m_drive
```

Install the resulting car kit using its README, or install the declared components through the
MGU Store. The generated kit's `deploy-car.sh install` installs the renderer persistently.
The renderer must be running and able to use the head unit's graphics driver and compositor.
The controller gate loads with the HMI at the next head-unit start.

Keep M Drive's **Renderer** setting on **Automatic**. The header shows **GPU** for the native path
or **SOFTWARE** for fallback. In the native full-screen settings sheet, **Rendering status** shows
FPS when the renderer has reported it. The HMI's fallback settings screen has no dynamic status row.
The app does not claim 60 FPS from a connection alone.

If the service is absent or the foreground gate cannot show M Drive, the app keeps working through
the HMI's software path. It switches automatically when the native renderer becomes available.
There is no forced GPU-only mode that would leave a blank dashboard.

## Verify on the head unit

Run this read-only helper on the head unit:

```sh
sh renderer-status.sh
```

The script is in `deploy/car/renderer-status.sh` and is included in the generated car kit.
It reports renderer services, sockets, graphics driver lines, and any existing performance log lines.
It does not restart the renderer or change vehicle state.

The renderer's `GL:` startup line identifies the graphics implementation. An Intel hardware driver
on the actual MGU establishes the GPU used. Software GL implementations such as llvmpipe do not
establish physical GPU acceleration. A Mac emulator or a VM cannot establish your car's FPS.

The native renderer also sends FPS and draw-time statistics to connected apps. For journal
statistics, its upstream diagnostic switch is `/run/mgu-render/stats-log`. During a parked test,
create that file, open M Drive with changing RPM, and read the journal:

```sh
mkdir -p /run/mgu-render
touch /run/mgu-render/stats-log
journalctl --no-pager -f -u idrive7-renderd -u mgu-renderd -u mgu-render
```

Look for `stats m_drive`, its measured FPS, render time, and `path layer`. Finish journal monitoring
with Ctrl+C and remove only the diagnostic flag:

```sh
rm /run/mgu-render/stats-log
```

This enables renderer logging only. The checks need shell access to the head unit; this repository
has not measured M Drive on a physical car.

## Repeat the host protocol check

```sh
node kit/tools/benchmark_m_drive_rendering.js
```

This runs the staged app with changing signal samples and a compositor stand-in that acknowledges
frames at 60 Hz. It checks native command delivery, explicit software fallback, automatic recovery
when the renderer appears, and idle-frame suppression. The reported rates are host protocol and
software-image callback rates, not physical GPU measurements or BMW HMI transport benchmarks.
Use `--out /absolute/path/report.json` to save the measurements.

The app's control state and request guards are exercised separately by `test_m_drive.js`. Selecting
the native renderer does not arm car controls or change diagnostic polling.
