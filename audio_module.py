import gc, time, warnings, numpy, soundcard
from PyQt6.QtCore import QThread, pyqtSignal

warnings.filterwarnings( "ignore", category = soundcard.SoundcardRuntimeWarning )

class AudioThread( QThread ):
    audio_data_ready = pyqtSignal( object )
    devices_ready = pyqtSignal( list )
    stats_ready = pyqtSignal( float, int, int )

    def __init__( self, num_bars = 100, sensitivity = 1.0, fps = 30 ):
        super().__init__()
        self.running = True
        self.device_name = None
        self.num_bars = num_bars
        self.sensitivity = sensitivity
        self.target_fps_interval = 1.0 / fps if fps > 0 else 0.033
        self.log_indices = None
        self.nonempty_bin_count = 0
        self._active_device = None
        self._last_frame_time = 0.0
        self._stats_started_at = time.monotonic()
        self._stats_frame_count = 0

    def _update_bins( self, fft_len ):
        discrete_len = max( 1, fft_len )
        indices = numpy.logspace( 0, numpy.log10( discrete_len ), self.num_bars + 1, dtype = int, )
        indices[ 0 ] = 0
        indices[ -1 ] = discrete_len
        for index in range( 1, len( indices ) ):
            indices[ index ] = max( indices[ index ], indices[ index - 1 ] + 1 )
        for index in range( len( indices ) - 2, 0, -1 ):
            indices[ index ] = min( indices[ index ], indices[ index + 1 ] - 1 )
        self.log_indices = indices
        self.nonempty_bin_count = sum(
            1
            for start, end in zip( indices[ :-1 ], indices[ 1: ] )
            if start < fft_len and min( end, fft_len ) > start
        )
        #gc.collect()

    def _build_bands( self, fft ):
        if self.log_indices is None or len( self.log_indices ) - 1 != self.num_bars:
            self._update_bins( len( fft ) )
        bands = []
        for i in range( len( self.log_indices ) - 1 ):
            start = self.log_indices[ i ]
            end = max( start + 1, self.log_indices[ i + 1 ] )
            chunk = fft[ start:end ]
            band_avg = numpy.mean( chunk ) if len( chunk ) > 0 else 0
            freq_boost = 1.0 + ( i / max( 1, self.num_bars ) ) * 12.0
            val = min( 100, int( band_avg * self.sensitivity * freq_boost ) )
            bands.append( val )
        return bands
    
    def _reset_stats( self ):
        self._stats_started_at = time.monotonic()
        self._stats_frame_count = 0

    def _process_audio_frame( self, data ):
        current_time = time.monotonic()
        if current_time - self._last_frame_time < self.target_fps_interval:
            return None
        self._last_frame_time = current_time
        mono = data[ :, 0 ]
        fft = numpy.abs( numpy.fft.rfft( mono ) )
        bands = self._build_bands( fft )
        self._stats_frame_count += 1
        stats_elapsed = time.monotonic() - self._stats_started_at
        if stats_elapsed >= 1.0:
            self.stats_ready.emit( self._stats_frame_count / stats_elapsed, self.num_bars, self.nonempty_bin_count, )
            self._reset_stats()
        return bands[: self.num_bars ]
    
    def update_parameters( self, num_bars, sensitivity, fps ):
        self.num_bars = num_bars
        self.sensitivity = sensitivity
        self.target_fps_interval = 1.0 / fps if fps > 0 else 0.033
        self.log_indices = None

    def run( self ):
        try:
            all_devices = soundcard.all_microphones( include_loopback = True )
            self.devices_ready.emit( [ dev.name for dev in all_devices ] )
        except Exception as exc:
            print( f"Error fetching audio devices: { exc }" )
            return
        while self.running:
            if not self.device_name:
                self.msleep( 100 )
                continue
            try:
                if self._active_device != self.device_name:
                    self._active_device = self.device_name
                    self._last_frame_time = 0.0
                    self._reset_stats()
                mic = soundcard.get_microphone( id = self.device_name, include_loopback = True )
                with mic.recorder( samplerate = 44100 ) as recorder:
                    while self.running and self.device_name == mic.name:
                        data = recorder.record( numframes = 2048 )
                        if len( data ) == 0:
                            self.msleep( 5 )
                            continue
                        bands = self._process_audio_frame( data )
                        if bands is not None:
                            self.audio_data_ready.emit( bands )
            except Exception as exc:
                print( f"Audio Error: { exc }" )
                self._active_device = None
                self.msleep( 500 )

    def set_device( self, name ):
        self.device_name = name
        self._active_device = None
        self._last_frame_time = 0.0
        self._reset_stats()

    def stop( self ):
        self.running = False
        self._active_device = None
        self.wait()
        gc.collect()