package com.example.sdkdemo.feature;

import android.Manifest;
import android.annotation.SuppressLint;
import android.content.res.Configuration;
import android.os.Bundle;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.widget.LinearLayoutCompat;
import androidx.appcompat.widget.SwitchCompat;

import com.blankj.utilcode.util.PermissionUtils;
import com.example.sdkdemo.R;
import com.example.sdkdemo.ScreenUtil;
import com.example.sdkdemo.base.BasePlayActivity;
import com.example.sdkdemo.util.AssetsUtil;
import com.volcengine.androidcloud.common.log.AcLog;
import com.volcengine.androidcloud.common.model.StreamStats;
import com.volcengine.cloudcore.common.mode.AudioPlaybackDevice;
import com.volcengine.cloudcore.common.mode.LocalAudioStreamError;
import com.volcengine.cloudcore.common.mode.LocalAudioStreamState;
import com.volcengine.cloudcore.common.mode.LocalStreamStats;
import com.volcengine.cloudphone.apiservice.AudioService;
import com.volcengine.cloudphone.apiservice.outinterface.IPlayerListener;
import com.volcengine.cloudphone.apiservice.outinterface.IStreamListener;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import org.json.JSONException;
import org.json.JSONObject;

import java.util.Map;

/**
 * 该类用于展示与音频{@link AudioService}相关的功能接口
 */
public class AudioServiceActivity extends BasePlayActivity
        implements IPlayerListener, IStreamListener {

    private final String TAG = "AudioServiceActivity";

    private ViewGroup mContainer;
    private PhonePlayConfig mPhonePlayConfig;
    private PhonePlayConfig.Builder mBuilder;
    private AudioService mAudioService;
    private SwitchCompat mSwShowOrHide, mSwSendAudio;
    private LinearLayoutCompat mLlButtons;
    private Button mBtnMute, mBtnVolumeUp, mBtnVolumeDown, mBtnGetSettings,
            mBtnStartSendAudio, mBtnStopSendAudio, mBtnChangeAudioPlaybackDevice;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        setContentView(R.layout.activity_audio);
        initView();
        initPhonePlayConfig();
    }

    private void initView() {
        mContainer = findViewById(R.id.container);
        mSwShowOrHide = findViewById(R.id.sw_show_or_hide);
        mLlButtons = findViewById(R.id.ll_buttons);
        mBtnMute = findViewById(R.id.btn_mute);
        mBtnVolumeUp = findViewById(R.id.btn_volume_up);
        mBtnVolumeDown = findViewById(R.id.btn_volume_down);
        mSwSendAudio = findViewById(R.id.sw_send_audio);
        mBtnStartSendAudio = findViewById(R.id.btn_start_send_audio);
        mBtnStopSendAudio = findViewById(R.id.btn_stop_send_audio);
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
        });

        mBtnStartSendAudio.setOnClickListener(view -> {
            if (mAudioService != null) {
                requestPermissionAndStartSendAudio();
            }
        });

        mBtnStopSendAudio.setOnClickListener(view -> {
            if (mAudioService != null) {
                /**
                 * stopSendAudioStream() -- 关闭音频数据发送，并且不进行音频采集
                 */
                mAudioService.stopSendAudioStream();
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
                 */
                showToast("本地设备播放音量: " + mAudioService.getLocalAudioPlaybackVolume() + "\n" +
                        "远端实例播放音量: " + mAudioService.getRemoteAudioPlaybackVolume() + "\n" +
                        "本地设备采集音量: " + mAudioService.getLocalAudioCaptureVolume() + "\n" +
                        "是否发送音频流: " + mAudioService.isSendingAudioStream() + "\n" +
                        "是否正在发送音频流: " + mAudioService.isEnableSendAudioStream());
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
        });
    }

    private void initPhonePlayConfig() {
        /**
         * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * *
         * ak/sk/token用于用户鉴权，需要从火山官网上获取，具体步骤详见README[鉴权相关]。
         * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * *
         *
         * ak/sk/token/podId的值从assets目录下的sts.json文件中读取，该目录及文件需要自行创建。
         * sts.json的格式形如
         * {
         *     "podId": "your_pod_id",
         *     "productId": "your_product_id",
         *     "ak": "your_ak",
         *     "sk": "your_sk",
         *     "token": "your_token"
         * }
         */
        String ak = "", sk = "", token = "", podId = "", productId = "";  // 这里需要替换成你的 ak/sk/token/podId/productId
        String sts = AssetsUtil.getTextFromAssets(this.getApplicationContext(), "sts.json");
        try {
            JSONObject stsJObj = new JSONObject(sts);
            ak = stsJObj.getString("ak");
            sk = stsJObj.getString("sk");
            token = stsJObj.getString("token");
            podId = stsJObj.getString("podId");
            productId = stsJObj.getString("productId");
        } catch (JSONException e) {
            e.printStackTrace();
        }

        String roundId = "roundId_123";
        String userId = "userId_" + System.currentTimeMillis();

        mBuilder = new PhonePlayConfig.Builder();
        mBuilder.userId(userId)
                .ak(ak)
                .sk(sk)
                .token(token)
                .container(mContainer)
                .enableLocalKeyboard(true)
                .roundId(roundId)
                .podId(podId)
                .productId(productId)
                .streamListener(this);

        mPhonePlayConfig = mBuilder.build();
        VePhoneEngine.getInstance().start(mPhonePlayConfig, this);
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
    }

    @Override
    public void finish() {
        VePhoneEngine.getInstance().stop();
        super.finish();
    }

    @Override
    public void onConfigurationChanged(@NonNull Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        AcLog.d(TAG, "[onConfigurationChanged] newConfig: " + newConfig.orientation);
        VePhoneEngine.getInstance().rotate(newConfig.orientation);
    }

    /**
     * 播放成功回调
     *
     * @param roundId 当次会话生命周期标识符
     * @param clarityId 当前画面的清晰度，首帧渲染到画面时触发该回调
     */
    @Override
    public void onPlaySuccess(String roundId, int clarityId) {
        AcLog.d(TAG, "[onPlaySuccess] roundId " + roundId + " clarityId " + clarityId);
    }

    /**
     * SDK内部产生的错误回调
     *
     * @param errorCode 错误码
     * @param errorMessage 错误详情
     */
    @Override
    public void onError(int errorCode, String errorMessage) {
        AcLog.e(TAG, "[onError] errorCode: " + errorCode + ", errorMessage: " + errorMessage);
        Toast.makeText(this, "[onError] errorCode: " + errorCode + ", errorMessage: " + errorMessage, Toast.LENGTH_SHORT).show();
    }

    /**
     * SDK内部产生的警告回调
     *
     * @param warningCode 警告码
     * @param warningMessage 警告详情
     */
    @Override
    public void onWarning(int warningCode, String warningMessage) {
        AcLog.d(TAG, "[onWarning] warningCode: " + warningCode + ", warningMessage: " + warningMessage);
    }

    /**
     * 网络连接类型和状态切换回调
     *
     * @param networkType 当前的网络类型
     *         -1 -- 网络连接类型未知
     *          0 -- 网络连接已断开
     *          1 -- 网络类型为 LAN
     *          2 -- 网络类型为 Wi-Fi（包含热点）
     *          3 -- 网络类型为 2G 移动网络
     *          4 -- 网络类型为 3G 移动网络
     *          5 -- 网络类型为 4G 移动网络
     *          6 -- 网络类型为 5G 移动网络
     */
    @Override
    public void onNetworkChanged(int networkType) {
        AcLog.d(TAG, "[onNetworkChanged] networkType: " + networkType);
    }

    /**
     * 即将废弃，建议使用{@link IPlayerListener#onServiceInit(Map)}
     */
    @Override
    public void onServiceInit() {

    }

    /**
     * 加入房间前回调，用于获取并初始化各个功能服务，例如设置各种事件监听回调。
     */
    @Override
    public void onServiceInit(@NonNull Map<String, Object> extras) {
        AcLog.d(TAG, "[onServiceInit] extras: " + extras);
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
                    AcLog.d(TAG, "[onRemoteAudioPlaybackVolumeChanged] volume: " + volume);
                }

                /**
                 * 远端实例请求开启本地音频推流回调
                 */
                @Override
                public void onRemoteAudioStartRequest() {
                    AcLog.d(TAG, "[onRemoteAudioStartRequest]");
                    requestPermissionAndStartSendAudio();
                }

                /**
                 * 远端实例请求关闭本地音频推流回调
                 */
                @Override
                public void onRemoteAudioStopRequest() {
                    AcLog.d(TAG, "[onRemoteAudioStopRequest]");
                    mAudioService.stopSendAudioStream();
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
                    AcLog.d(TAG, "[onAudioPlaybackDeviceChanged] device: " + device);
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
                    AcLog.d(TAG, "[onLocalAudioStateChanged] localAudioStreamState: " + localAudioStreamState +
                            ", localAudioStreamError: " + localAudioStreamError);
                }
            });
        }
    }

    /**
     * 收到音频首帧时的回调
     *
     * @param audioStreamId 远端实例音频流的ID
     */
    @Override
    public void onFirstAudioFrame(String audioStreamId) {
        AcLog.d(TAG, "[onFirstAudioFrame] audioStreamId: " + audioStreamId);
    }

    /**
     * 收到视频首帧时的回调
     *
     * @param videoStreamId 远端实例视频流的ID
     */
    @Override
    public void onFirstRemoteVideoFrame(String videoStreamId) {
        AcLog.d(TAG, "[onFirstRemoteVideoFrame] videoStreamId: " + videoStreamId);
    }

    /**
     * 开始播放的回调
     */
    @Override
    public void onStreamStarted() {
        AcLog.d(TAG, "[onStreamStarted]");
    }

    /**
     * 暂停播放后的回调，调用{@link VePhoneEngine#pause()}后会触发
     */
    @Override
    public void onStreamPaused() {
        AcLog.d(TAG, "[onStreamPaused]");
    }

    /**
     * 恢复播放后的回调，调用{@link VePhoneEngine#resume()} 或 VePhoneEngine#muteAudio(false) 后会触发
     */
    @Override
    public void onStreamResumed() {
        AcLog.d(TAG, "[onStreamResumed]");
    }

    /**
     * 周期为2秒的音视频网络状态的回调，可用于内部数据分析或监控
     *
     * @param streamStats 远端视频流的性能状态
     */
    @Override
    public void onStreamStats(StreamStats streamStats) {
        AcLog.d(TAG, "[onStreamStats] streamStats: " + streamStats);
    }

    /**
     * 周期为2秒的本地推送的音视频流的状态回调
     *
     * @param localStreamStats 本地音视频流的性能状态
     */
    @Override
    public void onLocalStreamStats(LocalStreamStats localStreamStats) {
        AcLog.d(TAG, "[onLocalStreamStats] localStreamStats: " + localStreamStats);
    }

    /**
     * 视频流连接状态变化
     *
     * @param state 视频流连接状态
     *              1 -- 连接断开
     *              2 -- 首次连接，正在连接中
     *              3 -- 首次连接成功
     *              4 -- 连接断开后，重新连接中
     *              5 -- 连接断开后，重新连接成功
     *              6 -- 连接断开超过10秒，但仍然会继续连接
     *              7 -- 连接失败，不会继续连接
     */
    @Override
    public void onStreamConnectionStateChanged(int state) {
        AcLog.d(TAG, "[onStreamConnectionStateChanged] connectionState: " + state);
    }

    /**
     * 操作延迟回调
     *
     * @param elapse 操作延迟的具体值，单位:毫秒
     */
    @Override
    public void onDetectDelay(long elapse) {
        AcLog.d(TAG, "[onDetectDelay] detectDelay: " + elapse);
    }

    /**
     * 客户端的旋转回调
     *
     * 远端实例通过该回调向客户端发送视频流的方向(横屏或竖屏)，为保证视频流方向与Activity方向一致，
     * 需要在该回调中根据rotation参数，调用 {@link BasePlayActivity#setRotation(int)} 来调整Activity的方向，
     * 0/180需将Activity调整为竖屏，90/270则将Activity调整为横屏；
     * 同时，需要在 {@link MessageChannelActivity#onConfigurationChanged(Configuration)} 回调中，
     * 根据当前Activity的方向，调用 {@link VePhoneEngine#rotate(int)} 来调整视频流的方向。
     *
     * @param rotation 旋转方向
     *          0, 180 -- 竖屏
     *         90, 270 -- 横屏
     */
    @Override
    public void onRotation(int rotation) {
        AcLog.d(TAG, "[onRotation] rotation: " + rotation);
        setRotation(rotation);
    }

    /**
     * 远端实例退出回调
     *
     * @param reasonCode 退出的原因码
     * @param reasonMessage 退出的原因详情
     */
    @Override
    public void onPodExit(int reasonCode, String reasonMessage) {
        AcLog.d(TAG, "[onPodExit] reasonCode: " + reasonCode + ", reasonMessage: " + reasonMessage);
    }

    /**
     * 周期为2秒的游戏中的网络质量回调
     *
     * @param quality 网络质量评级
     *                0 -- 网络状况未知，无法判断网络质量
     *                1 -- 网络状况极佳，能够高质量承载当前业务
     *                2 -- 当前网络状况良好，能够较好地承载当前业务
     *                3 -- 当前网络状况有轻微劣化，但不影响正常使用
     *                4 -- 当前网络质量欠佳，会影响当前业务的主观体验
     *                5 -- 当前网络已经无法承载当前业务的媒体流，需要采取相应策略，
     *                      比如降低媒体流的码率或者更换网络
     *                6 -- 当前网络完全无法正常通信
     */
    @Override
    public void onNetworkQuality(int quality) {
        AcLog.d(TAG, "[onNetworkQuality] quality: " + quality);
    }

    private void requestPermissionAndStartSendAudio() {
        PermissionUtils.permission(Manifest.permission.RECORD_AUDIO)
                .callback(new PermissionUtils.SimpleCallback() {
                    @SuppressLint("MissingPermission")
                    @Override
                    public void onGranted() {
                        /**
                         * startSendAudioStream() -- 获取麦克风权限后，采集并发送音频数据
                         */
                        mAudioService.startSendAudioStream();
                    }

                    @Override
                    public void onDenied() {
                        showToast("无录音权限");
                    }
                }).request();
    }

}
