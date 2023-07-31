package com.example.sdkdemo.feature;

import android.Manifest;
import android.annotation.SuppressLint;
import android.content.Context;
import android.util.Log;
import android.util.SparseIntArray;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.RadioGroup;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.Toast;

import androidx.appcompat.widget.SwitchCompat;

import com.blankj.utilcode.util.PermissionUtils;
import com.example.sdkdemo.R;
import com.volcengine.cloudcore.common.mode.AudioPlaybackDevice;
import com.volcengine.cloudcore.common.mode.LocalAudioStreamError;
import com.volcengine.cloudcore.common.mode.LocalAudioStreamState;
import com.volcengine.cloudphone.apiservice.AudioService;
import com.volcengine.phone.VePhoneEngine;

import java.util.Locale;

public class AudioServiceView extends ScrollView implements AudioService.AudioControlListener {
    private final SeekBar mSbLocalAudioPlaybackVolume;
    private final SeekBar mSbRemoteAudioPlaybackVolume;
    private final SparseIntArray mDeviceArray = new SparseIntArray();
    private final RadioGroup mRgAudioPlaybackDevice;
    private final SeekBar mSbLocalAudioCaptureVolume;
    private final Button mBtnLocalAudioPlaybackVolume;
    private final Button mBtnRemoteAudioPlaybackVolume;
    private final Button mBtnLocalAudioCaptureVolume;
    private final AudioService mAudioService;
    private static final String TAG = "AudioServiceView";

    {
        mDeviceArray.put(R.id.rb_headset, AudioPlaybackDevice.HEADSET);
        mDeviceArray.put(R.id.rb_earpiece, AudioPlaybackDevice.EARPIECE);
        mDeviceArray.put(R.id.rb_speakerphone, AudioPlaybackDevice.SPEAKERPHONE);
        mDeviceArray.put(R.id.rb_bluetooth_headset, AudioPlaybackDevice.HEADSET_BLUETOOTH);
    }

    public AudioServiceView(Context context, AudioService audioService) {
        super(context);
        this.mAudioService = audioService;
        inflate(context, R.layout.dialog_audio, this);

        setLayoutParams(new LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        /**
         * setAudioControlListener(AudioService.AudioControlListener listener) -- 设置音频控制监听器
         */
        mAudioService.setAudioControlListener(this);
        VePhoneEngine engine = VePhoneEngine.getInstance();

        /**
         * muteAudio(boolean mute) -- 云端实例静音开关
         */
        findViewById(R.id.btn_mute).setOnClickListener(v -> {
            engine.muteAudio(!engine.isAudioMuted());
        });

        /**
         * volumeDown() -- 降低云端实例音量大小
         */
        findViewById(R.id.btn_volumeDown).setOnClickListener(v -> {
            engine.volumeDown();
        });

        /**
         * volumeUp() -- 升高云端实例音量大小
         */
        findViewById(R.id.btn_volumeUp).setOnClickListener(v -> {
            engine.volumeUp();
        });

        /**
         * isEnableSendAudioStream() -- 是否发送音频流至云端实例
         * setEnableSendAudioStream(boolean enable) -- 设置是否发送音频流至云端实例
         */
        SwitchCompat switchCompat = findViewById(R.id.switch_enable);
        switchCompat.setChecked(mAudioService.isEnableSendAudioStream());
        switchCompat.setOnCheckedChangeListener((compoundButton, b) -> mAudioService.setEnableSendAudioStream(b));

        findViewById(R.id.btn_start_send_audio).setOnClickListener(view -> onRemoteAudioStartRequest());
        findViewById(R.id.btn_stop_send_audio).setOnClickListener(view -> onRemoteAudioStopRequest());

        /**
         * getLocalAudioPlaybackVolume() -- 获取本地设备播放音量
         */
        mSbLocalAudioPlaybackVolume = findViewById(R.id.sb_local_audio_playback_volume);
        mBtnLocalAudioPlaybackVolume = findViewById(R.id.btn_local_audio_playback_volume);
        mBtnLocalAudioPlaybackVolume.setOnClickListener(view -> {
            int volume = mAudioService.getLocalAudioPlaybackVolume();
            mSbLocalAudioPlaybackVolume.setProgress(volume);
            mBtnLocalAudioPlaybackVolume.setText(String.format(Locale.getDefault(), "get[%d]", volume));
        });
        mSbLocalAudioPlaybackVolume.setProgress(mAudioService.getLocalAudioPlaybackVolume());
        mSbLocalAudioPlaybackVolume.setOnSeekBarChangeListener(mOnSeekBarChangeListener);

        /**
         * getRemoteAudioPlaybackVolume() -- 获取远端实例播放音量
         */
        mSbRemoteAudioPlaybackVolume = findViewById(R.id.sb_remote_audio_playback_volume);
        mSbRemoteAudioPlaybackVolume.setProgress(mAudioService.getRemoteAudioPlaybackVolume());
        mBtnRemoteAudioPlaybackVolume = findViewById(R.id.btn_remote_audio_playback_volume);
        mBtnRemoteAudioPlaybackVolume.setOnClickListener(view -> {
            int volume = mAudioService.getRemoteAudioPlaybackVolume();
            mSbRemoteAudioPlaybackVolume.setProgress(volume);
            mBtnRemoteAudioPlaybackVolume.setText(String.format(Locale.getDefault(), "get[%d]", volume));
        });
        mSbRemoteAudioPlaybackVolume.setOnSeekBarChangeListener(mOnSeekBarChangeListener);

        /**
         * getLocalAudioCaptureVolume() -- 获取本地设备采集音量
         */
        mSbLocalAudioCaptureVolume = findViewById(R.id.sb_local_audio_capture_volume);
        mSbLocalAudioCaptureVolume.setProgress(mAudioService.getLocalAudioCaptureVolume());
        mBtnLocalAudioCaptureVolume = findViewById(R.id.btn_local_audio_capture_volume);
        mBtnLocalAudioCaptureVolume.setOnClickListener(view -> {
            int volume = mAudioService.getLocalAudioCaptureVolume();
            mSbLocalAudioCaptureVolume.setProgress(volume);
            mBtnLocalAudioCaptureVolume.setText(String.format(Locale.getDefault(), "get[%d]", volume));
        });
        mSbLocalAudioCaptureVolume.setOnSeekBarChangeListener(mOnSeekBarChangeListener);

        /**
         * getAudioPlaybackDevice() -- 获取本地音频播放设备
         */
        mRgAudioPlaybackDevice = findViewById(R.id.rg_audio_playback_device);
        int audioPlaybackDevice = mAudioService.getAudioPlaybackDevice();
        for (int i = 0; i < mDeviceArray.size(); i++) {
            int id = mDeviceArray.keyAt(i);
            if (mDeviceArray.get(id) == audioPlaybackDevice) {
                mRgAudioPlaybackDevice.check(id);
            }
        }
        mRgAudioPlaybackDevice.setOnCheckedChangeListener(mOnCheckedChangeListener);
    }

    private final SeekBar.OnSeekBarChangeListener mOnSeekBarChangeListener = new SeekBar.OnSeekBarChangeListener() {
        @Override
        public void onProgressChanged(SeekBar seekBar, int i, boolean b) {
            if (seekBar == mSbLocalAudioCaptureVolume) {
                mBtnLocalAudioCaptureVolume.setText(String.format(Locale.getDefault(), "get[%d]", i));
            } else if (seekBar == mSbRemoteAudioPlaybackVolume) {
                mBtnRemoteAudioPlaybackVolume.setText(String.format(Locale.getDefault(), "get[%d]", i));
            } else if (seekBar == mSbLocalAudioPlaybackVolume) {
                mBtnLocalAudioPlaybackVolume.setText(String.format(Locale.getDefault(), "get[%d]", i));
            }
        }

        @Override
        public void onStartTrackingTouch(SeekBar seekBar) {
        }

        @Override
        public void onStopTrackingTouch(SeekBar seekBar) {
            /**
             * setLocalAudioCaptureVolume(int volume) -- 设置本地设备采集音量
             * setRemoteAudioPlaybackVolume(int volume) -- 设置远端实例播放音量
             * setLocalAudioPlaybackVolume(int volume) -- 设置本地设备播放音量
             *
             * @param volume 音量大小，[0, 100]
             */
            int i = seekBar.getProgress();
            if (seekBar == mSbLocalAudioCaptureVolume) {
                mAudioService.setLocalAudioCaptureVolume(i);
            } else if (seekBar == mSbRemoteAudioPlaybackVolume) {
                mAudioService.setRemoteAudioPlaybackVolume(i);
            } else if (seekBar == mSbLocalAudioPlaybackVolume) {
                mAudioService.setLocalAudioPlaybackVolume(i);
            }
        }
    };

    /**
     * setAudioPlaybackDevice(int device) -- 设置本地音频输出设备，包含不限于系统扬声器和外接扬声器和耳机(有线耳机、蓝牙耳机)
     *
     * @param device 音频输出设备ID
     */
    private final RadioGroup.OnCheckedChangeListener mOnCheckedChangeListener = new RadioGroup.OnCheckedChangeListener() {
        @Override
        public void onCheckedChanged(RadioGroup radioGroup, int i) {
            int device = mDeviceArray.get(i);
            Log.d(TAG, "onCheckedChanged: device = " + device);
            mAudioService.setAudioPlaybackDevice(device);
        }
    };


    /**
     * 远端实例音量大小改变回调
     *
     * @param volume 返回的远端实例音量大小，[0,100]
     */
    @Override
    public void onRemoteAudioPlaybackVolumeChanged(int volume) {
        Log.d(TAG, "onRemoteAudioPlaybackVolumeChanged() called with: volume = [" + volume + "]");
        mSbRemoteAudioPlaybackVolume.setProgress(volume);
    }

    /**
     * 远端实例请求开启本地音频推流回调
     */
    @Override
    public void onRemoteAudioStartRequest() {
        Log.d(TAG, "onRemoteAudioStartRequest() called");
        PermissionUtils.permission(Manifest.permission.RECORD_AUDIO)
                .callback(new PermissionUtils.SimpleCallback() {
                    @SuppressLint("MissingPermission")
                    @Override
                    public void onGranted() {
                        mAudioService.startSendAudioStream();
                        Log.d(TAG, "startSendAudioStream: " + mAudioService.isSendingAudioStream());
                    }

                    @Override
                    public void onDenied() {
                        Toast.makeText(getContext(), "无录音权限", Toast.LENGTH_SHORT).show();
                    }
                }).request();
    }

    /**
     * 远端实例请求关闭本地音频推流回调
     */
    @Override
    public void onRemoteAudioStopRequest() {
        Log.d(TAG, "onRemoteAudioStopRequest() called");
        mAudioService.stopSendAudioStream();
        Log.d(TAG, "stopSendAudioStream: " + mAudioService.isSendingAudioStream());
    }

    /**
     * 本地音频播放设备改变回调
     *
     * @param device 本地音频播放设备
     *              -1 -- 未知
     *               1 -- 有线耳机
     *               2 -- 听筒
     *               3 -- 扬声器
     *               4 -- 蓝牙耳机
     *               5 -- USB设备
     */
    @Override
    public void onAudioPlaybackDeviceChanged(int device) {
        Log.d(TAG, "onAudioPlaybackDeviceChanged() called with: device = [" + device + "]");
        for (int i = 0; i < mDeviceArray.size(); i++) {
            int id = mDeviceArray.keyAt(i);
            if (mDeviceArray.get(id) == device) {
                mRgAudioPlaybackDevice.setOnCheckedChangeListener(null);
                mRgAudioPlaybackDevice.check(id);
                mRgAudioPlaybackDevice.setOnCheckedChangeListener(mOnCheckedChangeListener);
            }
        }
    }

    /**
     * 本地音频流状态改变回调
     *
     * @param localAudioStreamState 本地音频流状态
     * @param localAudioStreamError 本地音频流错误码
     */
    @Override
    public void onLocalAudioStateChanged(LocalAudioStreamState localAudioStreamState, LocalAudioStreamError localAudioStreamError) {

    }
}
