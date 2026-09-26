import numpy,warnings,time,json,soundcard,gc
from PyQt6.QtCore import QThread, pyqtSignal
warnings.filterwarnings("ignore", category=soundcard.SoundcardRuntimeWarning)

class AudioThread(QThread):
    audio_data_ready = pyqtSignal(str)
    devices_ready = pyqtSignal(list)
    stats_ready = pyqtSignal(float, int, int)
    def __init__(self, num_bars=100, sensitivity=1.0, fps=30):
        super().__init__()
        self.running = True
        self.device_name = None
        self.num_bars = num_bars
        self.sensitivity = sensitivity
        self.target_fps_interval = 1.0 / fps if fps > 0 else 0.033
        self.log_indices = None
        self.nonempty_bin_count = 0
    def _update_bins(self, fft_len):
        indices = numpy.logspace(
            0,
            numpy.log10(fft_len),
            self.num_bars + 1,
            dtype=int,
        )
        indices[0] = 0
        indices[-1] = fft_len
        for index in range(1, len(indices)):
            indices[index] = max(indices[index], indices[index - 1] + 1)
        for index in range(len(indices) - 2, 0, -1):
            indices[index] = min(indices[index], indices[index + 1] - 1)
        self.log_indices = indices
        self.nonempty_bin_count = sum(
            1
            for start, end in zip(indices[:-1], indices[1:])
            if start < fft_len and min(end, fft_len) > start
        )
    def update_parameters(self, num_bars, sensitivity, fps):
        self.num_bars = num_bars
        self.sensitivity = sensitivity
        self.target_fps_interval = 1.0 / fps if fps > 0 else 0.033
        self.log_indices = None
    def run(self):
        try:
            all_devices = soundcard.all_microphones(include_loopback=True)
            device_names = [dev.name for dev in all_devices]
            self.devices_ready.emit(device_names)
        except Exception as e:
            print(f"Error fetching audio devices: {e}")
            return
        last_time = 0
        stats_started_at = time.monotonic()
        stats_frame_count = 0
        while self.running:
            if not self.device_name:
                self.msleep(100)
                continue
            try:
                mic = soundcard.get_microphone(id=self.device_name, include_loopback=True)
                stats_started_at = time.monotonic()
                stats_frame_count = 0
                with mic.recorder(samplerate=44100) as recorder:
                    while self.running and self.device_name == mic.name:
                        data = recorder.record(numframes=2048)
                        if len(data) > 0:
                            current_time = time.time()
                            if current_time - last_time < self.target_fps_interval:
                                continue
                            last_time = current_time
                            mono = data[:, 0]
                            fft = numpy.abs(numpy.fft.rfft(mono))
                            fft_len = len(fft)
                            if self.log_indices is None or len(self.log_indices) - 1 != self.num_bars:
                                self._update_bins(fft_len)
                            bands = []
                            for i in range(len(self.log_indices) - 1):
                                start = self.log_indices[i]
                                end = max(start + 1, self.log_indices[i+1])
                                chunk = fft[start:end]
                                band_avg = numpy.mean(chunk) if len(chunk) > 0 else 0
                                freq_boost = 1.0 + (i / max(1, self.num_bars)) * 12.0 
                                val = min(100, int(band_avg * self.sensitivity * freq_boost))
                                bands.append(val)
                            self.audio_data_ready.emit(json.dumps(bands[:self.num_bars]))
                            stats_frame_count += 1
                            stats_elapsed = time.monotonic() - stats_started_at
                            if stats_elapsed >= 1.0:
                                self.stats_ready.emit(
                                    stats_frame_count / stats_elapsed,
                                    self.num_bars,
                                    self.nonempty_bin_count,
                                )
                                stats_frame_count = 0
                                stats_started_at = time.monotonic()
            except Exception as e:
                print(f"Audio Error: {e}")
                self.msleep(500)
    def set_device(self, name):
        self.device_name = name
    def stop(self):
        self.running = False
        self.wait()
        gc.collect()