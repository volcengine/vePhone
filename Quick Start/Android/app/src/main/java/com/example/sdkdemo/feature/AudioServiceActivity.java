package com.example.sdkdemo.feature;

import android.Manifest;
import android.annotation.SuppressLint;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.widget.LinearLayoutCompat;
import androidx.appcompat.widget.SwitchCompat;

import com.blankj.utilcode.util.PermissionUtils;
import com.example.sdkdemo.R;
import com.example.sdkdemo.base.BasePlayActivity;
import com.example.sdkdemo.util.AudioRecordThread;
import com.example.sdkdemo.util.ScreenUtil;
import com.example.sdkdemo.util.SdkUtil;
import com.volcengine.cloudcore.common.mode.AudioPlaybackDevice;
import com.volcengine.cloudcore.common.mode.LocalAudioStreamError;
import com.volcengine.cloudcore.common.mode.LocalAudioStreamState;
import com.volcengine.cloudphone.apiservice.AudioService;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import java.text.MessageFormat;
import java.util.Map;

/**
 * 该类用于展示与音频{@link AudioService}相关的功能接口
 * 使用该服务可以实现云端实例对本地音频的采集，采集方式包括内部采集与外部采集。
 * 内部采集使用本地麦克风等设备进行音频采集，不进行加工处理直接发送给云端实例；
 * 外部采集可以对本地采集的音频进行一定的加工处理，再发送给云端实例。
 */
public class AudioServiceActivity extends BasePlayActivity {

    private ViewGroup mContainer;
    private AudioService mAudioService;
    private AudioRecordThread mAudioRecordThread;
    private SwitchCompat mSwShowOrHide, mSwSendAudio;
    private LinearLayoutCompat mLlButtons;
    private Button mBtnMute, mBtnVolumeUp, mBtnVolumeDown, mBtnGetSettings,
            mBtnSetJBDelay, mBtnChangeAudioPlaybackDevice;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        setContentView(R.layout.activity_audio);
        initView();
        initPlayConfigAndStartPlay();
    }

    private void initView() {
        mContainer = findViewById(R.id.container);
        mSwShowOrHide = findViewById(R.id.sw_show_or_hide);
        mLlButtons = findViewById(R.id.ll_buttons);
        mBtnMute = findViewById(R.id.btn_mute);
        mBtnVolumeUp = findViewById(R.id.btn_volume_up);
        mBtnVolumeDown = findViewById(R.id.btn_volume_down);
        mSwSendAudio = findViewById(R.id.sw_send_audio);
        mBtnSetJBDelay = findViewById(R.id.btn_set_jitter_buffer);
        mBtnGetSettings = findViewById(R.id.btn_get_settings);
        mBtnChangeAudioPlaybackDevice = findViewById(R.id.btn_change_audio_playback_device);

        mSwShowOrHide.setOnCheckedChangeListener((buttonView, isChecked) -> {
            mLlButtons.setVisibility(isChecked ? View.VISIBLE : View.GONE);
        });

        mBtnMute.setOnClickListener(view -> {
            /**
             * isAudioMuted() -- 查询云端实例是否静音
             * muteAudio(boolean mute) -- 云端实例静音开关
             */
            VePhoneEngine.getInstance().muteAudio(!VePhoneEngine.getInstance().isAudioMuted());
        });
        mBtnVolumeUp.setOnClickListener(view -> {
            /**
             * volumeUp() -- 升高云端实例音量大小
             */
            VePhoneEngine.getInstance().volumeUp();
        });
        mBtnVolumeDown.setOnClickListener(view -> {
            /**
             * volumeDown() -- 降低云端实例音量大小
             */
            VePhoneEngine.getInstance().volumeDown();
        });

        mSwSendAudio.setOnCheckedChangeListener((compoundButton, enable) -> {
            if (mAudioService != null) {
                /**
                 * setEnableSendAudioStream(boolean enable) -- 设置是否向云端实例发送音频流
                 */
                mAudioService.setEnableSendAudioStream(enable);
            }
            else {
                Log.e(TAG, "mAudioService == null");
            }
        });

        mBtnSetJBDelay.setOnClickListener(view -> {
            if (mAudioService != null) {
                /**
                 * setJitterBufferDelay(int delay) -- 设置音频JitterBuffer缓冲时长，单位: ms
                 * 当 delay<30ms 时，SDK内部会处理成30以防止过低；可以通过设置 delay=0 使延迟时间恢复到正常值
                 */
                mAudioService.setJitterBufferDelay(0);
            }
        });

        mBtnGetSettings.setOnClickListener(view -> {
            if (mAudioService != null) {
                /**
                 * getLocalAudioPlaybackVolume() -- 获取本地设备播放音量
                 * getRemoteAudioPlaybackVolume() -- 获取远端实例播放音量
                 * getLocalAudioCaptureVolume() -- 获取本地设备采集音量
                 * isEnableSendAudioStream() -- 是否向云端实例发送音频流
                 * isSendingAudioStream() -- 是否正在向云端实例发送音频流
                 * getJitterBufferDelay() -- 获取音频JitterBuffer缓冲时长，单位：ms
                 */
                showToast("本地设备播放音量: " + mAudioService.getLocalAudioPlaybackVolume() + "\n" +
                        "远端实例播放音量: " + mAudioService.getRemoteAudioPlaybackVolume() + "\n" +
                        "本地设备采集音量: " + mAudioService.getLocalAudioCaptureVolume() + "\n" +
                        "是否发送音频流: " + mAudioService.isEnableSendAudioStream() + "\n" +
                        "是否正在发送音频流: " + mAudioService.isSendingAudioStream() + "\n" +
                        "音频JitterBuffer缓冲时长: " + mAudioService.getJitterBufferDelay());
            }
            else {
                Log.e(TAG, "mAudioService == null");
            }
        });

        mBtnChangeAudioPlaybackDevice.setOnClickListener(view -> {
            if (mAudioService != null) {
                /**
                 * setAudioPlaybackDevice(int device) -- 设置本地音频输出设备，
                 * 包含不限于系统扬声器和外接扬声器和耳机(有线耳机、蓝牙耳机)
                 * 注意：切换外放设备需确保音频上传处于开启的状态，否则切换无效
                 *
                 * @param device 音频输出设备ID
                 */
                mAudioService.setAudioPlaybackDevice(
                        mAudioService.getAudioPlaybackDevice() == AudioPlaybackDevice.SPEAKERPHONE ?
                                AudioPlaybackDevice.EARPIECE : AudioPlaybackDevice.SPEAKERPHONE);
            }
            else {
                Log.e(TAG, "mAudioService == null");
            }
        });
    }

    private void initPlayConfigAndStartPlay() {
        SdkUtil.PlayAuth auth = SdkUtil.getPlayAuth(this);
        SdkUtil.checkPlayAuth(auth,
                p -> {
                    PhonePlayConfig.Builder builder = new PhonePlayConfig.Builder();
                    builder.userId(SdkUtil.getClientUid())
                            .ak(auth.ak)
                            .sk(auth.sk)
                            .token(auth.token)
                            .container(mContainer)
                            .enableLocalKeyboard(true)
                            .podId(auth.podId)
                            .productId(auth.productId)
                            .streamListener(this);
                    VePhoneEngine.getInstance().start(builder.build(), this);
                },
                p -> {
                    showTipDialog(MessageFormat.format(getString(R.string.invalid_phone_play_config) , p));
                });
    }

    @Override
    protected void onResume() {
        super.onResume();
        VePhoneEngine.getInstance().resume();
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    @Override
    protected void onPause() {
        super.onPause();
        VePhoneEngine.getInstance().pause();
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (mAudioRecordThread != null) {
            mAudioRecordThread.setRecordStatus(false);
            mAudioRecordThread = null;
        }
    }

    @Override
    public void finish() {
        VePhoneEngine.getInstance().stop();
        super.finish();
    }

    @Override
    public void onServiceInit(@NonNull Map<String, Object> extras) {
        super.onServiceInit(extras);
        mAudioService = VePhoneEngine.getInstance().getAudioService();
        if (mAudioService != null) {
            /**
             * setAudioControlListener(AudioControlListener listener) -- 设置音频控制监听器
             */
            mAudioService.setAudioControlListener(new AudioService.AudioControlListener() {
                /**
                 * 远端实例音量大小改变回调
                 *
                 * @param volume 返回的远端实例音量大小，[0,100]
                 */
                @Override
                public void onRemoteAudioPlaybackVolumeChanged(int volume) {
                    Log.i(TAG, "[onRemoteAudioPlaybackVolumeChanged] volume: " + volume);
                }

                /**
                 * 远端实例请求开启本地音频推流回调
                 */
                @Override
                public void onRemoteAudioStartRequest() {
                    Log.i(TAG, "[onRemoteAudioStartRequest]");
                    requestPermissionAndStartSendAudio();
                }

                /**
                 * 远端实例请求关闭本地音频推流回调
                 */
                @Override
                public void onRemoteAudioStopRequest() {
                    Log.i(TAG, "[onRemoteAudioStopRequest]");
                    /**
                     * (内部采集使用)
                     * stopSendAudioStream() -- 关闭音频数据发送，并且不进行音频采集
                     */
                    mAudioService.stopSendAudioStream();

                    /**
                     * (外部采集使用)
                     * 停止音频录制
                     */
//                    if (mAudioRecordThread != null) {
//                        mAudioRecordThread.setRecordStatus(false);
//                        mAudioRecordThread = null;
//                    }
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
                    Log.i(TAG, "[onAudioPlaybackDeviceChanged] device: " + device);
                    showToast("[onAudioPlaybackDeviceChanged] device: " + device);
                }

                /**
                 * 本地音频流状态改变回调
                 *
                 * @param localAudioStreamState 本地音频流状态
                 * @param localAudioStreamError 本地音频流错误码
                 */
                @Override
                public void onLocalAudioStateChanged(LocalAudioStreamState localAudioStreamState, LocalAudioStreamError localAudioStreamError) {
                    Log.i(TAG, "[onLocalAudioStateChanged] localAudioStreamState: " + localAudioStreamState +
                            ", localAudioStreamError: " + localAudioStreamError);
                }
            });
        }
        else {
            Log.e(TAG, "mAudioService == null");
        }
    }

    private void requestPermissionAndStartSendAudio() {
        PermissionUtils.permission(Manifest.permission.RECORD_AUDIO)
                .callback(new PermissionUtils.SimpleCallback() {
                    @SuppressLint("MissingPermission")
                    @Override
                    public void onGranted() {
                        /**
                         * (内部采集使用)
                         * startSendAudioStream() -- 获取麦克风权限后，采集并发送音频数据
                         */
                        mAudioService.startSendAudioStream();

                        /**
                         * (外部采集使用)
                         * 开始音频录制并发布外部采集的音频
                         */
//                        if (mAudioRecordThread == null) {
//                            mAudioRecordThread = new AudioRecordThread(mAudioService);
//                            mAudioRecordThread.start();
//                        }
                    }

                    @Override
                    public void onDenied() {
                        showToast("无录音权限");
                    }
                }).request();
    }

}
