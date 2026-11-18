import re
import subprocess
import sys
import numpy as np
import pyqtgraph as pg
from scipy.signal import lfilter, windows
from PySide6.QtCore import QRectF, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class AudioReaderThread(QThread):
    """Reads raw float32 mono PCM audio via parec (PulseAudio/PipeWire) or arecord (ALSA)."""
    audio_chunk = Signal(np.ndarray)
    error_occurred = Signal(str)

    def __init__(self, backend: str, device_id: str, sample_rate: int = 44100, chunk_samples: int = 1024):
        super().__init__()
        self.backend = backend
        self.device_id = device_id
        self.sample_rate = sample_rate
        self.chunk_bytes = chunk_samples * 4  # float32 = 4 bytes/sample
        self._running = True
        self.proc = None

    def run(self):
        if self.backend == "pulse":
            cmd = [
                "parec",
                "--format=float32le",
                f"--rate={self.sample_rate}",
                "--channels=1",
                "--latency-msec=25",
                "-d",
                self.device_id,
            ]
        else:
            cmd = [
                "arecord",
                "-D",
                self.device_id,
                "-f",
                "FLOAT_LE",
                "-r",
                str(self.sample_rate),
                "-c",
                "1",
                "-t",
                "raw",
                "-q",
            ]

        try:
            self.proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0
            )
        except Exception as e:
            self.error_occurred.emit(f"Failed to start {cmd[0]}: {e}")
            return

        while self._running and self.proc.poll() is None:
            data = self.proc.stdout.read(self.chunk_bytes)
            if not data:
                err = self.proc.stderr.read().decode(errors="ignore").strip()
                if err and self._running:
                    self.error_occurred.emit(f"Audio stream stopped:\n{err}")
                break
            usable = (len(data) // 4) * 4
            if usable > 0:
                samples = np.frombuffer(data[:usable], dtype=np.float32).copy()
                self.audio_chunk.emit(samples)

    def stop(self):
        self._running = False
        if self.proc is not None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.wait()


class AudioAnalyzerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Real-Time Audio Waveform, Spectrogram & Formant Analyzer")
        self.resize(1280, 800)

        # --- Audio & Optimized Spectrogram Parameters ---
        self.sample_rate = 44100
        self.spec_window_sec = 1.0    # 1.0 s rolling spectrogram
        self.waveform_sec = 1.0       # 1.0 s rolling waveform
        self.max_display_freq = 4000  # 0–4 kHz range

        self.nperseg = 1024
        self.nfft = 2048
        self.hop_size = 256

        self.freq_per_bin = self.sample_rate / self.nfft
        self.max_bin = int(np.ceil(self.max_display_freq / self.freq_per_bin)) + 1
        self.num_spec_slices = int(np.ceil((self.spec_window_sec * self.sample_rate) / self.hop_size))
        self.wave_buffer_len = int(self.waveform_sec * self.sample_rate)

        # Rolling buffers (shape: [time_slices, freq_bins] for col-major ImageItem)
        self.wave_buffer = np.zeros(self.wave_buffer_len, dtype=np.float32)
        self.spec_buffer = np.full((self.num_spec_slices, self.max_bin), -80.0, dtype=np.float32)
        self.stft_remainder = np.array([], dtype=np.float32)
        self.prev_sample = 0.0

        self.hann_win = windows.hann(self.nperseg, sym=False).astype(np.float32)
        self.win_scale = float(np.sum(self.hann_win)) / 2.0
        self.time_axis = np.linspace(-self.waveform_sec, 0, self.wave_buffer_len)

        self.reader_thread: AudioReaderThread | None = None

        self._init_ui()
        self.refresh_microphones()

        # 25 FPS (40 ms) UI & DSP refresh
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plots_and_metrics)
        self.timer.start(40)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # --- Top Bar: Microphone Selector & Formant Readouts ---
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("<b>Microphone:</b>"))

        self.mic_combo = QComboBox()
        self.mic_combo.setMinimumWidth(320)
        self.mic_combo.currentIndexChanged.connect(self.on_mic_changed)
        top_bar.addWidget(self.mic_combo)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_microphones)
        top_bar.addWidget(self.refresh_btn)

        top_bar.addSpacing(20)

        self.f0_box = self._create_readonly_box("F0 (Pitch):")
        self.f1_box = self._create_readonly_box("F1:")
        self.f2_box = self._create_readonly_box("F2:")

        for lbl, box in [self.f0_box, self.f1_box, self.f2_box]:
            top_bar.addWidget(lbl)
            top_bar.addWidget(box)
            top_bar.addSpacing(10)

        top_bar.addStretch()
        main_layout.addLayout(top_bar)

        # --- PyQtGraph Plots ---
        pg.setConfigOptions(antialias=False, imageAxisOrder="col-major")

        # 1. Live Waveform Plot (1.0 s window)
        self.wave_plot = pg.PlotWidget(title="Live Waveform (44.1 kHz, 1.0 s window)")
        self.wave_plot.setLabel("left", "Amplitude")
        self.wave_plot.setLabel("bottom", "Time", units="s")
        self.wave_plot.setYRange(-1.0, 1.0)
        self.wave_plot.setXRange(-self.waveform_sec, 0)
        self.wave_plot.showGrid(x=True, y=True, alpha=0.3)
        self.wave_curve = self.wave_plot.plot(
            self.time_axis,
            self.wave_buffer,
            pen=pg.mkPen("#00e5ff", width=1.0),
            downsample=4,
            downsampleMethod="peak",
        )
        main_layout.addWidget(self.wave_plot, stretch=1)

        # 2. Live Spectrogram Plot (1.0 s rolling window, 0–4 kHz)
        self.spec_plot = pg.PlotWidget(title="Live Spectrogram (1.0 s window, 0–4 kHz, Pre-emphasized)")
        self.spec_plot.setLabel("left", "Frequency", units="Hz")
        self.spec_plot.setLabel("bottom", "Time", units="s")
        self.spec_img = pg.ImageItem(axisOrder="col-major")
        self.spec_plot.addItem(self.spec_img)

        colormap = pg.colormap.get("magma", source="matplotlib")
        self.spec_img.setLookupTable(colormap.getLookupTable())
        self.spec_img.setLevels([-80.0, -15.0])

        dt = self.hop_size / self.sample_rate
        total_width = self.num_spec_slices * dt
        self.spec_rect = QRectF(
            -total_width,
            -0.5 * self.freq_per_bin,
            total_width,
            self.max_bin * self.freq_per_bin,
        )
        self.spec_img.setRect(self.spec_rect)
        self.spec_plot.setXRange(-self.spec_window_sec, 0, padding=0)
        self.spec_plot.setYRange(0, self.max_display_freq, padding=0)

        # Overlay lines for F0, F1, F2
        self.f0_line = pg.InfiniteLine(angle=0, pen=pg.mkPen("#00e5ff", width=1.5, style=Qt.PenStyle.DashLine))
        self.f1_line = pg.InfiniteLine(angle=0, pen=pg.mkPen("#69f0ae", width=1.5, style=Qt.PenStyle.DashLine))
        self.f2_line = pg.InfiniteLine(angle=0, pen=pg.mkPen("#ffd740", width=1.5, style=Qt.PenStyle.DashLine))
        self.spec_plot.addItem(self.f0_line)
        self.spec_plot.addItem(self.f1_line)
        self.spec_plot.addItem(self.f2_line)

        main_layout.addWidget(self.spec_plot, stretch=1)

    def _create_readonly_box(self, label_text: str) -> tuple[QLabel, QLineEdit]:
        lbl = QLabel(f"<b>{label_text}</b>")
        edit = QLineEdit("— Hz")
        edit.setReadOnly(True)
        edit.setFixedWidth(95)
        edit.setAlignment(Qt.AlignmentFlag.AlignRight)
        edit.setStyleSheet("background-color: #252526; color: #00e5ff; font-weight: bold; padding: 3px;")
        return lbl, edit

    def refresh_microphones(self):
        self.mic_combo.blockSignals(True)
        self.mic_combo.clear()

        devices = []
        default_src = ""

        # 1. Try PulseAudio / PipeWire via pactl
        try:
            info_out = subprocess.check_output(["pactl", "info"], text=True, stderr=subprocess.DEVNULL)
            for line in info_out.splitlines():
                if line.startswith("Default Source:"):
                    default_src = line.split(":", 1)[1].strip()

            src_out = subprocess.check_output(["pactl", "list", "sources"], text=True, stderr=subprocess.DEVNULL)
            cur_name, cur_desc = None, None
            for line in src_out.splitlines():
                line = line.strip()
                if line.startswith("Name:"):
                    cur_name = line.split("Name:", 1)[1].strip()
                elif line.startswith("Description:"):
                    cur_desc = line.split("Description:", 1)[1].strip()
                    if cur_name and not cur_name.endswith(".monitor"):
                        devices.append((cur_desc, ("pulse", cur_name)))
                    cur_name, cur_desc = None, None
        except Exception:
            pass

        # 2. Fallback to raw ALSA capture cards via arecord -l
        if not devices:
            try:
                alsa_out = subprocess.check_output(["arecord", "-l"], text=True, stderr=subprocess.DEVNULL)
                for line in alsa_out.splitlines():
                    m = re.match(
                        r"^card\s+(\d+):\s+([^\[]+)\[([^\]]+)\],\s+device\s+(\d+):\s+([^\[]+)\[([^\]]+)\]",
                        line,
                    )
                    if m:
                        card_idx, _, card_name, dev_idx, _, dev_name = m.groups()
                        hw_id = f"plughw:{card_idx},{dev_idx}"
                        devices.append((f"{card_name.strip()} - {dev_name.strip()} ({hw_id})", ("alsa", hw_id)))
            except Exception:
                pass

        default_idx = 0
        for idx, (label, payload) in enumerate(devices):
            self.mic_combo.addItem(label, userData=payload)
            if payload == ("pulse", default_src):
                default_idx = idx

        self.mic_combo.blockSignals(False)

        if not devices:
            QMessageBox.warning(
                self,
                "No Microphones Detected by Linux",
                "Neither PulseAudio/PipeWire nor ALSA (arecord -l) found a microphone.\n\n"
                "Check:\n"
                "• Is a microphone physically plugged in?\n"
                "• Run 'lsusb' or 'arecord -l' in terminal to verify hardware detection.",
            )
        else:
            self.mic_combo.setCurrentIndex(default_idx)
            self.start_stream(self.mic_combo.currentData())

    def on_mic_changed(self, combo_idx: int):
        payload = self.mic_combo.itemData(combo_idx)
        if payload is not None:
            self.start_stream(payload)

    def start_stream(self, payload: tuple[str, str]):
        backend, device_id = payload
        if self.reader_thread is not None:
            self.reader_thread.stop()
            self.reader_thread = None

        self.wave_buffer.fill(0)
        self.spec_buffer.fill(-80.0)
        self.stft_remainder = np.array([], dtype=np.float32)
        self.prev_sample = 0.0

        self.reader_thread = AudioReaderThread(backend, device_id, self.sample_rate)
        self.reader_thread.audio_chunk.connect(self._on_audio_chunk)
        self.reader_thread.error_occurred.connect(lambda msg: QMessageBox.critical(self, "Audio Error", msg))
        self.reader_thread.start()

    def _on_audio_chunk(self, samples: np.ndarray):
        # 1. Update rolling raw waveform buffer
        n = len(samples)
        if n >= self.wave_buffer_len:
            self.wave_buffer[:] = samples[-self.wave_buffer_len :]
        else:
            self.wave_buffer[:-n] = self.wave_buffer[n:]
            self.wave_buffer[-n:] = samples

        # 2. Apply continuous first-order pre-emphasis (y[n] = x[n] - 0.97*x[n-1])
        emph = np.empty_like(samples)
        emph[0] = samples[0] - 0.97 * self.prev_sample
        emph[1:] = samples[1:] - 0.97 * samples[:-1]
        self.prev_sample = float(samples[-1])

        # 3. Vectorized overlapping STFT (nperseg=1024, nfft=2048, hop=256)
        combined = np.concatenate([self.stft_remainder, emph])
        if len(combined) >= self.nperseg:
            num_frames = (len(combined) - self.nperseg) // self.hop_size + 1
            shape = (num_frames, self.nperseg)
            strides = (combined.strides[0] * self.hop_size, combined.strides[0])
            frames = np.lib.stride_tricks.as_strided(combined, shape=shape, strides=strides)

            windowed = frames * self.hann_win
            mag = np.abs(np.fft.rfft(windowed, n=self.nfft, axis=1))[:, : self.max_bin] / self.win_scale
            db_slices = 20.0 * np.log10(np.maximum(mag, 1e-6)).astype(np.float32)

            k = min(num_frames, self.num_spec_slices)
            self.spec_buffer[:-k] = self.spec_buffer[k:]
            self.spec_buffer[-k:] = db_slices[-k:]

            consumed = num_frames * self.hop_size
            self.stft_remainder = combined[consumed:]
        else:
            self.stft_remainder = combined

    def update_plots_and_metrics(self):
        # 1. Refresh Waveform
        self.wave_curve.setData(self.time_axis, self.wave_buffer)

        # 2. Refresh Spectrogram (enforce col-major orientation, dB bounds, and world rect)
        spec_snapshot = self.spec_buffer.copy()
        self.spec_img.setImage(spec_snapshot, autoLevels=False, levels=(-80.0, -15.0))
        self.spec_img.setRect(self.spec_rect)

        # 3. Analyze the latest 50 ms frame for F0, F1, F2
        analysis_len = int(0.05 * self.sample_rate)
        frame = self.wave_buffer[-analysis_len:].copy()

        rms = np.sqrt(np.mean(frame**2))
        if rms < 0.008:
            self.f0_box[1].setText("— Hz")
            self.f1_box[1].setText("— Hz")
            self.f2_box[1].setText("— Hz")
            return

        f0 = self.estimate_f0(frame, self.sample_rate)
        f1, f2 = self.estimate_formants_lpc(frame, self.sample_rate)

        self.f0_box[1].setText(f"{f0:.1f} Hz" if f0 > 0 else "— Hz")
        self.f1_box[1].setText(f"{f1:.0f} Hz" if f1 > 0 else "— Hz")
        self.f2_box[1].setText(f"{f2:.0f} Hz" if f2 > 0 else "— Hz")

        if f0 > 0:
            self.f0_line.setPos(f0)
        if f1 > 0:
            self.f1_line.setPos(f1)
        if f2 > 0:
            self.f2_line.setPos(f2)

    @staticmethod
    def estimate_f0(frame: np.ndarray, fs: int) -> float:
        frame = frame - np.mean(frame)
        windowed = frame * np.hanning(len(frame))
        corr = np.correlate(windowed, windowed, mode="full")[len(windowed) - 1 :]
        if corr[0] <= 0:
            return 0.0
        corr /= corr[0]

        min_lag = int(fs / 500)
        max_lag = int(fs / 70)
        if max_lag >= len(corr):
            return 0.0

        segment = corr[min_lag:max_lag]
        peak_idx = np.argmax(segment) + min_lag
        if corr[peak_idx] < 0.35:
            return 0.0

        if 0 < peak_idx < len(corr) - 1:
            y0, y1, y2 = corr[peak_idx - 1], corr[peak_idx], corr[peak_idx + 1]
            denom = y0 - 2 * y1 + y2
            if denom != 0:
                peak_idx += 0.5 * (y0 - y2) / denom

        return float(fs / peak_idx)

    @staticmethod
    def estimate_formants_lpc(frame: np.ndarray, fs: int) -> tuple[float, float]:
        pre_emph = lfilter([1.0, -0.97], [1.0], frame)
        dec_factor = 4
        sig = pre_emph[::dec_factor]
        fs_dec = fs / dec_factor
        sig = sig * np.hamming(len(sig))

        order = 12
        r = np.correlate(sig, sig, mode="full")[len(sig) - 1 : len(sig) + order]
        if r[0] <= 1e-10:
            return 0.0, 0.0

        a = np.zeros(order + 1)
        a[0] = 1.0
        err = r[0]

        for i in range(1, order + 1):
            acc = np.dot(a[1:i], r[i - 1 : 0 : -1])
            k = -(r[i] + acc) / err
            a[1:i] += k * a[i - 1 : 0 : -1]
            a[i] = k
            err *= 1.0 - k * k
            if err <= 0:
                break

        roots = np.roots(a)
        roots = roots[np.imag(roots) >= 0.01]
        angles = np.arctan2(np.imag(roots), np.real(roots))
        freqs = angles * (fs_dec / (2.0 * np.pi))
        bandwidths = -0.5 * (fs_dec / (2.0 * np.pi)) * np.log(np.abs(roots))

        formants = sorted(
            f for f, bw in zip(freqs, bandwidths) if 200.0 <= f <= 3500.0 and bw < 450.0
        )
        f1 = formants[0] if len(formants) >= 1 else 0.0
        f2 = formants[1] if len(formants) >= 2 else 0.0
        return float(f1), float(f2)

    def closeEvent(self, event):
        self.timer.stop()
        if self.reader_thread is not None:
            self.reader_thread.stop()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AudioAnalyzerApp()
    window.show()
    sys.exit(app.exec())