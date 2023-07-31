package com.example.sdkdemo.feature;

import static android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE;
import static android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_PORTRAIT;

import android.content.res.Configuration;
import android.os.Bundle;
import android.util.Log;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.Toast;

import androidx.annotation.IntRange;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.LinearLayoutCompat;
import androidx.appcompat.widget.SwitchCompat;

import com.blankj.utilcode.util.ToastUtils;
import com.example.sdkdemo.R;
import com.example.sdkdemo.ScreenUtil;
import com.example.sdkdemo.util.AssetsUtil;
import com.volcengine.androidcloud.common.log.AcLog;
import com.volcengine.androidcloud.common.model.StreamStats;
import com.volcengine.androidcloud.common.pod.Rotation;
import com.volcengine.cloudcore.common.mode.LocalStreamStats;
import com.volcengine.cloudcore.common.mode.VideoRenderMode;
import com.volcengine.cloudphone.apiservice.MultiMediaStreamService;
import com.volcengine.cloudphone.apiservice.outinterface.IPlayerListener;
import com.volcengine.cloudphone.apiservice.outinterface.IStreamListener;
import com.volcengine.cloudphone.base.VeAudioFrame;
import com.volcengine.cloudphone.base.VeDisplay;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import org.json.JSONException;
import org.json.JSONObject;

import java.text.MessageFormat;
import java.util.HashMap;
import java.util.Map;


/**
 * 该类用于展示与{@link MultiMediaStreamService}相关的功能接口的使用方法
 */
public class MultiMediaStreamActivity extends AppCompatActivity
        implements IPlayerListener, IStreamListener {

    private final String TAG = "MultiMediaStreamActivity";

    private FrameLayout mMainContainer, mSecondaryContainer;
    private PhonePlayConfig mPhonePlayConfig;
    private PhonePlayConfig.Builder mBuilder;
    private MultiMediaStreamService mMultiMediaStreamService;
    private SwitchCompat mSwShowOrHide;
    private LinearLayoutCompat mLlButtons;
    private EditText mEtStreamId, mEtClarityId, mEtAudioZone;
    private Button mBtnSubscribeStream, mBtnUnsubscribeStream, mBtnPauseStream, mBtnResumeStream;
    private Button mBtnMuteVideo, mBtnMuteAudio, mBtnSwitchClarity, mBtnSendTouchEvent, mBtnSendKeyEvent;
    private Button mBtnLaunchApp, mBtnCloseApp, mBtnGetStatus, mBtnSetAudioZone;
    private Button mBtnGetAudioZoneStatus, mBtnGetAudioFocusApp, mBtnGetFocusedWindowApp;
    private boolean mIsMuteVideo = true, mIsMuteAudio = true;


    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        setContentView(R.layout.activity_multi_media_stream);
        initView();
        initPhonePlayConfig();
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
        /**
         * 在多屏场景下，调用{@link VePhoneEngine#rotate(int)}方法只会旋转主屏的方向，
         * 若想旋转副屏的方向，需要调用{@link MultiMediaStreamService#rotate(String, int)}。
         */
        VePhoneEngine.getInstance().rotate(newConfig.orientation);
    }

    private void initView() {
        mMainContainer = findViewById(R.id.main_container);
        mSecondaryContainer = findViewById(R.id.secondary_container);
        mSwShowOrHide = findViewById(R.id.sw_show_or_hide);
        mLlButtons = findViewById(R.id.ll_buttons);
        mEtStreamId = findViewById(R.id.et_stream_id);
        mBtnSubscribeStream = findViewById(R.id.btn_subscribe_stream);
        mBtnUnsubscribeStream = findViewById(R.id.btn_unsubscribe_stream);
        mBtnPauseStream = findViewById(R.id.btn_pause_stream);
        mBtnResumeStream = findViewById(R.id.btn_resume_stream);
        mBtnMuteVideo = findViewById(R.id.btn_mute_video);
        mBtnMuteAudio = findViewById(R.id.btn_mute_audio);
        mEtClarityId = findViewById(R.id.et_clarity_id);
        mBtnSwitchClarity = findViewById(R.id.btn_switch_clarity);
        mBtnSendTouchEvent = findViewById(R.id.btn_send_touch_event);
        mBtnSendKeyEvent = findViewById(R.id.btn_send_key_event);
        mBtnLaunchApp = findViewById(R.id.btn_launch_app);
        mBtnCloseApp = findViewById(R.id.btn_close_app);
        mBtnGetStatus = findViewById(R.id.btn_get_status);
        mEtAudioZone = findViewById(R.id.et_audio_zone);
        mBtnSetAudioZone = findViewById(R.id.btn_set_audio_zone);
        mBtnGetAudioZoneStatus = findViewById(R.id.btn_get_audio_zone_status);
        mBtnGetAudioFocusApp = findViewById(R.id.btn_get_audio_focus_app);
        mBtnGetFocusedWindowApp = findViewById(R.id.btn_get_focused_window_app);

        mSwShowOrHide.setOnCheckedChangeListener((buttonView, isChecked) -> {
            mLlButtons.setVisibility(isChecked ? View.VISIBLE : View.GONE);
            mEtStreamId.setVisibility(isChecked ? View.VISIBLE : View.GONE);
        });

        /**
         * boolean isAudioMuted(String streamId)
         * 返回音频流是否暂停
         * @param streamId 音视频流ID
         * @return true -- 暂停
         *         false -- 非暂停
         *
         *
         * boolean isVideoMuted(String streamId)
         * 返回视频流是否暂停
         * @param streamId 音视频流ID
         * @return true -- 暂停
         *         false -- 非暂停
         *
         *
         * boolean isInterceptTouchEvent(String streamId)
         * 返回是否拦截触控事件
         * @param streamId 音视频流ID
         * @return true -- 拦截
         *         false -- 不拦截
         */
        mBtnGetStatus.setOnClickListener(v -> {
            if (mMultiMediaStreamService != null) {
                if (mEtStreamId.getText() != null && !mEtStreamId.getText().toString().isEmpty()) {
                    String str = "isAudioMuted: " + mMultiMediaStreamService.isAudioMuted(mEtStreamId.getText().toString())
                            + "\n isVideoMuted: " + mMultiMediaStreamService.isVideoMuted(mEtStreamId.getText().toString())
                            + "\n isInterceptTouchEvent: " + mMultiMediaStreamService.isInterceptTouchEvent(mEtStreamId.getText().toString());
                    ToastUtils.showShort(str);
                }
                else {
                    ToastUtils.showShort("请检查streamId是否为空");
                }
            }
        });

        /**
         * subscribeStream(@NonNull String streamId, @NonNull VeDisplay display)
         * 将streamID对应的音视频流放入streamContainer播放，并会主动拉起appID对应的App，默认订阅音视频
         *
         * @param streamId 音视频流ID
         * @param display  指定承载视频流的容器及其他参数
         */
        mBtnSubscribeStream.setOnClickListener(v -> {
            if (mMultiMediaStreamService != null) {
                if (mEtStreamId.getText() != null && !mEtStreamId.getText().toString().isEmpty()) {
                    if ("0-0".equals(mEtStreamId.getText().toString())) {
                        mMultiMediaStreamService.subscribeStream(mEtStreamId.getText().toString(),
                                new VeDisplay.Builder()
                                        .mainScreen(true)
                                        .container(mMainContainer)
                                        .build());
                    }
                    else {
                        mMultiMediaStreamService.subscribeStream(mEtStreamId.getText().toString(),
                                new VeDisplay.Builder()
                                        .mainScreen(false)
                                        .container(mSecondaryContainer)
                                        .build());
                    }
                }
                else {
                    ToastUtils.showShort("请检查streamId是否为空");
                }
            }
        });

        /**
         * unsubscribeStream(@NonNull String streamId)
         * 取消订阅流，默认包含音视频，同时会释放对subscribeStream()传入参数streamContainer的持有。
         * 需要重新执行subscribeStream()才能重新/恢复拉流。
         *
         * @param streamId 音视频流ID
         */
        mBtnUnsubscribeStream.setOnClickListener(v -> {
            if (mMultiMediaStreamService != null) {
                if (mEtStreamId.getText() != null && !mEtStreamId.getText().toString().isEmpty()) {
                    mMultiMediaStreamService.unsubscribeStream(mEtStreamId.getText().toString());
                }
                else {
                    ToastUtils.showShort("请检查streamId是否为空");
                }
            }
        });

        /**
         * pauseStream(@NonNull String streamId)
         * 暂停播放streamID对应的音视频流
         *
         * PS: 建议在暂停播放时，不发送触控事件；在恢复播放时，正常发送触控事件。
         *
         * @param streamId 音视频流ID
         *
         * setInterceptTouchEvent(String streamId, boolean isIntercept)
         * 拦截streamID对应音视频流的触控事件
         *
         * @param streamId 音视频流ID
         * @param isIntercept 是否拦截触控事件
         *                    true -- 拦截，即不再发送触控事件
         *                    false -- 不拦截，即正常发送触控事件
         */
        mBtnPauseStream.setOnClickListener(v -> {
            if (mMultiMediaStreamService != null) {
                if (mEtStreamId.getText() != null && !mEtStreamId.getText().toString().isEmpty()) {
                    mMultiMediaStreamService.pauseStream(mEtStreamId.getText().toString());
                    mMultiMediaStreamService.setInterceptTouchEvent(mEtStreamId.getText().toString(), true);
                }
                else {
                    ToastUtils.showShort("请检查streamId是否为空");
                }
            }
        });

        /**
         * resumeStream(@NonNull String streamId)
         * 恢复播放streamID对应的音视频流
         *
         * @param streamId 音视频流ID
         */
        mBtnResumeStream.setOnClickListener(v -> {
            if (mMultiMediaStreamService != null) {
                if (mEtStreamId.getText() != null && !mEtStreamId.getText().toString().isEmpty()) {
                    mMultiMediaStreamService.resumeStream(mEtStreamId.getText().toString());
                    mMultiMediaStreamService.setInterceptTouchEvent(mEtStreamId.getText().toString(), false);
                }
                else {
                    ToastUtils.showShort("请检查streamId是否为空");
                }
            }
        });

        /**
         * muteVideo(String streamId, boolean mute)
         * 设置视频流的开关状态
         *
         * PS: 建议在关闭音视频流时，不发送触控事件；在开启音视频流时，正常发送触控事件。
         *
         * @param streamId 音视频流ID
         * @param mute 是否开启视频流
         *             true -- 关闭视频流
         *             false -- 开启视频流
         */
        mBtnMuteVideo.setOnClickListener(v -> {
            if (mMultiMediaStreamService != null) {
                if (mEtStreamId.getText() != null && !mEtStreamId.getText().toString().isEmpty()) {
                    mBtnMuteVideo.setText(mIsMuteVideo ? "视频: 关" : "视频: 开");
                    mMultiMediaStreamService.muteVideo(mEtStreamId.getText().toString(), mIsMuteVideo);
                    mMultiMediaStreamService.setInterceptTouchEvent(mEtStreamId.getText().toString(), mIsMuteVideo);
                    mIsMuteVideo = !mIsMuteVideo;
                }
                else {
                    ToastUtils.showShort("请检查streamId是否为空");
                }
            }
        });

        /**
         * muteAudio(String streamId, boolean mute)
         * 设置音频流的开关状态
         *
         * @param streamId 音视频流ID
         * @param mute 是否开启音频流
         *             true -- 关闭音频流
         *             false -- 开启音频流
         */
        mBtnMuteAudio.setOnClickListener(v -> {
            if (mMultiMediaStreamService != null) {
                if (mEtStreamId.getText() != null && !mEtStreamId.getText().toString().isEmpty()) {
                    mBtnMuteAudio.setText(mIsMuteAudio ? "音频: 关" : "音频: 开");
                    mMultiMediaStreamService.muteAudio(mEtStreamId.getText().toString(), mIsMuteAudio);
                    mIsMuteAudio = !mIsMuteAudio;
                }
                else {
                    ToastUtils.showShort("请检查streamId是否为空");
                }
            }
        });

        /**
         * int switchVideoStreamProfileId(String streamId, int streamProfileId)
         * 切换streamId对应的音视频流的清晰度档位
         *
         * @param streamId        音视频流ID
         * @param streamProfileId 清晰度档位
         * @return  0 -- 方法调用成功
         *          1 -- 方法调用失败
         */
        mBtnSwitchClarity.setOnClickListener(v -> {
            if (mMultiMediaStreamService != null) {
                if (mEtStreamId.getText() != null && !mEtStreamId.getText().toString().isEmpty()
                        && mEtClarityId.getText() != null && !mEtClarityId.getText().toString().isEmpty()) {
                    mMultiMediaStreamService.switchVideoStreamProfileId(
                            mEtStreamId.getText().toString(), Integer.parseInt(mEtClarityId.getText().toString()));
                }
                else {
                    ToastUtils.showShort("请检查streamId或clarityId是否为空");
                }
            }
        });

        /**
         * int sendMotionEvent(String streamId, MotionEvent event)
         * 向streamId对应的音视频流发送触摸事件
         *
         * @param streamId 音视频流ID
         * @param event 触摸事件
         *
         * @return  0 -- 方法调用成功
         *          1 -- 方法调用失败
         *
         * int sendMotionEvent(String streamId,
         *                         int action,
         *                         @FloatRange(from = 0.0, to = 1.0) float offsetX,
         *                         @FloatRange(from = 0.0, to = 1.0) float offsetY)
         *
         * @param streamId 音视频流ID
         * @param action 比如:
         *                  {@link MotionEvent#ACTION_DOWN}
         *                  {@link MotionEvent#ACTION_UP}
         *                  {@link MotionEvent#ACTION_CANCEL}
         *                  {@link MotionEvent#ACTION_POINTER_DOWN}
         *                  {@link MotionEvent#ACTION_POINTER_UP}
         *                  {@link MotionEvent#ACTION_MOVE}
         *
         * @return  0 -- 方法调用成功
         *          1 -- 方法调用失败
         */
        mBtnSendTouchEvent.setOnClickListener(v -> {
            if (mMultiMediaStreamService != null) {
                if (mEtStreamId.getText() != null && !mEtStreamId.getText().toString().isEmpty()) {
                    mMultiMediaStreamService.sendMotionEvent(mEtStreamId.getText().toString(), MotionEvent.ACTION_DOWN, 0.5f, 0.9f);
                    mMultiMediaStreamService.sendMotionEvent(mEtStreamId.getText().toString(), MotionEvent.ACTION_MOVE, 0.6f, 0.9f);
                    mMultiMediaStreamService.sendMotionEvent(mEtStreamId.getText().toString(), MotionEvent.ACTION_UP, 0.6f, 0.9f);
                }
                else {
                    ToastUtils.showShort("请检查streamId是否为空");
                }
            }
        });

        /**
         * int sendKeyEvent(String streamId, int keyCode)
         * 向streamId对应的音视频流发送键盘事件
         *
         * @param streamId 音视频流ID
         * @param keyCode 键盘事件码，当前只支持以下键盘事件:
         *                {@link KeyEvent#KEYCODE_HOME}
         *                {@link KeyEvent#KEYCODE_BACK}
         *                {@link KeyEvent#KEYCODE_MENU}
         *                {@link KeyEvent#KEYCODE_APP_SWITCH}
         * @return  0 -- 方法调用成功
         *          1 -- 方法调用失败或不支持该keyCode
         */
        mBtnSendKeyEvent.setOnClickListener(v -> {
            if (mMultiMediaStreamService != null) {
                if (mEtStreamId.getText() != null && !mEtStreamId.getText().toString().isEmpty()) {
                    mMultiMediaStreamService.sendKeyEvent(mEtStreamId.getText().toString(), KeyEvent.KEYCODE_BACK);
                }
                else {
                    ToastUtils.showShort("请检查streamId是否为空");
                }
            }
        });

        /**
         * int launchApp(String streamId, String pkgName)
         * 将指定应用在streamId对应的音视频流上启动
         *
         * @param streamId 音视频流ID
         * @param pkgName 应用包名
         * @return  0 -- 方法调用成功
         *          1 -- 方法调用失败
         */
        mBtnLaunchApp.setOnClickListener(v -> {
            if (mMultiMediaStreamService != null) {
                if (mEtStreamId.getText() != null && !mEtStreamId.getText().toString().isEmpty()) {
                    mMultiMediaStreamService.launchApp(mEtStreamId.getText().toString(), "com.bytedance.byteautoservice");
                }
                else {
                    ToastUtils.showShort("请检查streamId是否为空");
                }
            }
        });

        /**
         * int closeApp(String streamId, String pkgName)
         * 关闭streamId对应的音视频流上的指定应用
         *
         * @param streamId 音视频流ID
         * @param pkgName 应用包名
         * @return  0 -- 方法调用成功
         *          1 -- 方法调用失败
         */
        mBtnCloseApp.setOnClickListener(v -> {
            if (mMultiMediaStreamService != null) {
                if (mEtStreamId.getText() != null && !mEtStreamId.getText().toString().isEmpty()) {
                    mMultiMediaStreamService.closeApp(mEtStreamId.getText().toString(), "com.bytedance.byteautoservice");
                }
                else {
                    ToastUtils.showShort("请检查streamId是否为空");
                }
            }
        });

        /**
         * int setStreamForAudioZone(@IntRange(from = 0) int audioZone, String streamId)
         * 绑定音区到指定音视频流，设置结果通过{@link MultiMediaStreamService.AudioZoneListener#onSetResult(int, int, String, String)}返回
         *
         * @param audioZone 音区
         * @param streamId 音视频流ID
         * @return 0 -- 方法调用成功
         *        -1 -- 方法调用失败
         */
        mBtnSetAudioZone.setOnClickListener(v -> {
            if (mMultiMediaStreamService != null) {
                if (mEtStreamId.getText() != null && !mEtStreamId.getText().toString().isEmpty()
                        && mEtAudioZone.getText() != null && !mEtAudioZone.getText().toString().isEmpty()) {
                    mMultiMediaStreamService.setStreamForAudioZone(
                            Integer.parseInt(mEtAudioZone.getText().toString()), mEtStreamId.getText().toString());
                }
                else {
                    ToastUtils.showShort("请检查streamId或audioZone是否为空");
                }
            }
        });

        /**
         * int getStreamForAudioZone(@IntRange(from = 0) int audioZone)
         * 查询音区当前绑定的音视频流，查询结果通过{@link MultiMediaStreamService.AudioZoneListener#onGetResult(int, int, String, String)}返回
         *
         * @param audioZone 音区
         * @return 0 -- 方法调用成功
         *        -1 -- 方法调用失败
         */
        mBtnGetAudioZoneStatus.setOnClickListener(v -> {
            if (mMultiMediaStreamService != null) {
                if (mEtAudioZone.getText() != null && !mEtAudioZone.getText().toString().isEmpty()) {
                    mMultiMediaStreamService.getStreamForAudioZone(Integer.parseInt(mEtAudioZone.getText().toString()));
                }
                else {
                    ToastUtils.showShort("请检查audioZone是否为空");
                }
            }
        });

        /**
         * int getAudioFocusApp(@IntRange(from = 0) int audioZone)
         * 获取指定音区当前焦点应用包名，结果通过{@link MultiMediaStreamService.MultiAudioFocusAppListener#onResult(int, int, String, String, String)}返回
         *
         * @param audioZone 音区
         * @return 0 -- 方法调用成功
         *        -1 -- 方法调用失败
         */
        mBtnGetAudioFocusApp.setOnClickListener(v -> {
            if (mMultiMediaStreamService != null) {
                if (mEtAudioZone.getText() != null && !mEtAudioZone.getText().toString().isEmpty()) {
                    mMultiMediaStreamService.getAudioFocusApp(Integer.parseInt(mEtAudioZone.getText().toString()));
                }
                else {
                    ToastUtils.showShort("请检查audioZone是否为空");
                }
            }
        });

        /**
         * int getFocusedWindowApp(String streamId)
         * 获取指定屏幕当前焦点应用包名，结果通过{@link MultiMediaStreamService.MultiFocusedWindowAppListener#onResult(String, int, String, String)}返回
         *
         * @param streamId 音视频流ID
         * @return 0 -- 方法调用成功
         *        -1 -- 方法调用失败
         */
        mBtnGetFocusedWindowApp.setOnClickListener(v -> {
            if (mMultiMediaStreamService != null) {
                if (mEtStreamId.getText() != null && !mEtStreamId.getText().toString().isEmpty()) {
                    mMultiMediaStreamService.getFocusedWindowApp(mEtStreamId.getText().toString());
                }
                else {
                    ToastUtils.showShort("请检查streamId是否为空");
                }
            }
        });
    }

    private void initPhonePlayConfig() {
        /**
         * 这里需要替换成你的 ak/sk/token
         */
        String ak = "", sk = "", token = "";
        String sts = AssetsUtil.getTextFromAssets(this.getApplicationContext(), "sts.json");
        try {
            JSONObject stsJObj = new JSONObject(sts);
            ak = stsJObj.getString("ak");
            sk = stsJObj.getString("sk");
            token = stsJObj.getString("token");
        } catch (JSONException e) {
            e.printStackTrace();
        }

        /**
         * 这里需要替换成你的 podId和productId
         */
        String podId = "7257048056544221996";
        String productId = "1677237029647159296";
        String roundId = "roundId_123";
        String userId = "userId_" + System.currentTimeMillis();

        /**
         * VeDisplay指定了取流的屏幕参数，其包含多个配置，详见{@link VeDisplay.Builder}
         */
        Map<String, VeDisplay> displayMap = new HashMap<>();
        displayMap.put("0-0", new VeDisplay.Builder()
                .container(mMainContainer) // 指定当前屏幕渲染视图的容器，必填项
                .mainScreen(true) // 指定当前屏幕是否为主屏，当有多个屏幕时只允许有一个主屏，非必填项
                .videoStreamProfileId(16310) // 指定当前屏幕的清晰度档位，非必填项
                .build());
        displayMap.put("0-1", new VeDisplay.Builder()
                .container(mSecondaryContainer)
                .mainScreen(false)
                .videoStreamProfileId(16310)
                .build());

        mBuilder = new PhonePlayConfig.Builder();
        mBuilder.userId(userId)
                .ak(ak)
                .sk(sk)
                .token(token)
                .container(mMainContainer)
                .roundId(roundId)
                .podId(podId)
                .videoStreamProfileId(16310)
                .videoRenderMode(VideoRenderMode.VIDEO_RENDER_MODE_FILL)
                .productId(productId)
                .enableLocalKeyboard(false)
                .displayList(displayMap)
                .debugConfig("{\"boe\":\"true\"}")
                .streamListener(this);

        mPhonePlayConfig = mBuilder.build();
        VePhoneEngine.getInstance().start(mPhonePlayConfig, this);
    }

    @Override
    public void onPlaySuccess(String roundId, int clarityId) {
        AcLog.d(TAG, "[onPlaySuccess] roundId " + roundId + " clarityId " + clarityId);
    }

    @Override
    public void onError(int i, String s) {
        AcLog.e(TAG, "[onError] errorCode: " + i + ", errorMsg: " + s);
    }

    @Override
    public void onWarning(int i, String s) {
        AcLog.w(TAG, "[onWarning] errorCode: " + i + ", errorMsg: " + s);
    }

    @Override
    public void onNetworkChanged(int i) {
        AcLog.d(TAG, "[onNetworkChanged] network: " + i);
    }

    @Override
    public void onServiceInit(@NonNull Map<String, Object> extras) {
        AcLog.d(TAG, "[onServiceInit] extras: " + extras);
        mMultiMediaStreamService = VePhoneEngine.getInstance().getMultiMediaStreamService();
        if (mMultiMediaStreamService != null) {
            /**
             * void setAppStateListener(AppStateListener listener)
             * 设置应用飞屏监听器
             *
             * @param listener 应用飞屏监听器
             */
            mMultiMediaStreamService.setAppStateListener(new MultiMediaStreamService.AppStateListener() {
                /**
                 * 当应用触发飞屏时收到此回调
                 *
                 * @param srcStreamId 飞屏前屏幕推流的音视频流ID
                 * @param dstStreamId 飞屏后屏幕推流的音视频流ID
                 * @param packageName 应用包名
                 */
                @Override
                public void onAppDisplayIdChanged(String srcStreamId, String dstStreamId, String packageName) {
                    AcLog.d(TAG, "onAppDisplayIdChanged: srcStreamId = [" + srcStreamId + "], dstStreamId = [" + dstStreamId + "], packageName = [" + packageName + "]");
                    ToastUtils.showShort("onAppDisplayIdChanged: srcStreamId = [" + srcStreamId + "], dstStreamId = [" + dstStreamId + "], packageName = [" + packageName + "]");
                }
            });

            /**
             * void setMultiStreamListener(MultiStreamListener listener)
             * 设置多屏取流监听器
             *
             * @param listener 多屏取流监听器
             */
            mMultiMediaStreamService.setMultiStreamListener(new MultiMediaStreamService.MultiStreamListener() {
                /**
                 * 当播放音视频成功时收到此回调
                 *
                 * @param streamId           音视频流ID
                 * @param videoStreamProfile 清晰度档位
                 * @param extraInfo          扩展信息
                 */
                @Override
                public void onPlaySuccess(String streamId, int videoStreamProfile, String extraInfo) {
                    AcLog.d(TAG, "onPlaySuccess: streamId = [" + streamId + "], videoStreamProfile = [" + videoStreamProfile + "], extraInfo = [" + extraInfo + "]");
                    ToastUtils.showShort("onPlaySuccess: streamId = [" + streamId + "], videoStreamProfile = [" + videoStreamProfile + "], extraInfo = [" + extraInfo + "]");
                }

                /**
                 * 当音视频流发生错误时收到此回调
                 *
                 * @param code 0-成功；其他为错误码
                 * @param msg  提示信息
                 */
                @Override
                public void onStreamError(int code, String msg) {
                    AcLog.d(TAG, "onStreamError: code = [" + code + "], msg = [" + msg + "]");
                    ToastUtils.showShort("onStreamError: code = [" + code + "], msg = [" + msg + "]");
                }

                /**
                 * 当接收到远端音频帧时收到此回调
                 *
                 * @param streamId 音视频流ID
                 * @param frame    音频帧
                 */
                @Override
                public void onReceivedRemoteAudioFrame(String streamId, VeAudioFrame frame) {
                    AcLog.d(TAG, "onReceivedRemoteAudioFrame: streamId = [" + streamId + "], frame = [" + frame + "]");
                }

                /**
                 * 当远端实例屏幕旋转时收到此回调，建议在该回调旋转副屏的方向
                 *
                 * @param streamId 音视频流ID
                 * @param rotation 0、180-竖屏；270、90-横屏
                 * @see Rotation#toRotation()
                 */
                @Override
                public void onRotate(String streamId, int rotation) {
                    AcLog.d(TAG, "onRotate: streamId = [" + streamId + "], rotation = [" + rotation + "]");
                    if (mMultiMediaStreamService != null) {
                        mMultiMediaStreamService.rotate(streamId, Rotation.from(rotation).orientation);
                    }
                }

                /**
                 * 当音视频流清晰度发生变化时收到此回调
                 *
                 * @param streamId 音视频流ID
                 * @param from 原清晰度档位
                 * @param current 当前清晰度档位
                 */
                @Override
                public void onStreamProfileChanged(String streamId, int from, int current) {
                    AcLog.d(TAG, "onStreamProfileChanged: streamId = [" + streamId + "], from = [" + from + "], current = [" + current + "]");
                    ToastUtils.showShort("onStreamProfileChanged: streamId = [" + streamId + "], from = [" + from + "], current = [" + current + "]");
                }

                /**
                 * 音视频流的当前性能状态回调
                 *
                 * @param streamId 音视频流ID
                 * @param streamStats 性能统计数据
                 */
                @Override
                public void onStreamStats(String streamId, StreamStats streamStats) {
                    AcLog.d(TAG, "onStreamStats: streamId = [" + streamId + "], streamStats = [" + streamStats + "]");
                }

                /**
                 * 网络质量等级回调
                 *
                 * @param streamId 音视频流ID
                 * @param quality 网络质量评级，eg.
                 *                {@link StreamStats#NETWORK_QUALITY_UNKNOWN}
                 *                {@link StreamStats#NETWORK_QUALITY_EXCELLENT}
                 *                {@link StreamStats#NETWORK_QUALITY_GOOD}
                 *                {@link StreamStats#NETWORK_QUALITY_POOR}
                 *                {@link StreamStats#NETWORK_QUALITY_BAD}
                 *                {@link StreamStats#NETWORK_QUALITY_VERY_BAD}
                 *                {@link StreamStats#NETWORK_QUALITY_DOWN}
                 */
                @Override
                public void onNetworkQuality(String streamId, int quality) {
                    AcLog.d(TAG, "onNetworkQuality: streamId = [" + streamId + "], quality = [" + quality + "]");
                }

                /**
                 * 当收到远端首帧音频帧时收到此回调
                 *
                 * @param streamId 远端实例音视频流ID
                 */
                @Override
                public void onFirstAudioFrame(String streamId) {
                    AcLog.d(TAG, "onFirstAudioFrame: streamId = [" + streamId + "]");
                }

                /**
                 * 当收到远端首帧视频帧时收到此回调
                 *
                 * @param streamId 远端实例音视频流ID
                 */
                @Override
                public void onFirstRemoteVideoFrame(String streamId) {
                    AcLog.d(TAG, "onFirstRemoteVideoFrame: streamId = [" + streamId + "]");
                }
            });

            /**
             * void setAudioZoneListener(AudioZoneListener listener)
             * 设置音区变化监听器
             *
             * @param listener 音区变化监听器
             */
            mMultiMediaStreamService.setAudioZoneListener(new MultiMediaStreamService.AudioZoneListener() {
                /**
                 * 当主动查询指定音区绑定的视频流时收到此回调
                 *
                 * @param audioZone 音区ID
                 * @param code      状态码：0-查询成功；其他-查询失败
                 * @param streamId  音视频流ID
                 * @param msg       错误信息
                 */
                @Override
                public void onGetResult(int audioZone, int code, String streamId, String msg) {
                    AcLog.d(TAG, "onGetResult: audioZone = [" + audioZone + "], code = [" + code + "], streamId = [" + streamId + "], msg = [" + msg + "]");
                    ToastUtils.showShort("onGetResult: audioZone = [" + audioZone + "], code = [" + code + "], streamId = [" + streamId + "], msg = [" + msg + "]");
                }

                /**
                 * 当绑定音区到指定的视频流时收到此回调
                 *
                 * @param audioZone 音区ID
                 * @param code      状态码：0-设置成功；其他-设置失败
                 * @param streamId  音视频流ID
                 * @param msg       错误信息
                 */
                @Override
                public void onSetResult(int audioZone, int code, String streamId, String msg) {
                    AcLog.d(TAG, "onSetResult: audioZone = [" + audioZone + "], code = [" + code + "], streamId = [" + streamId + "], msg = [" + msg + "]");
                    ToastUtils.showShort("onSetResult: audioZone = [" + audioZone + "], code = [" + code + "], streamId = [" + streamId + "], msg = [" + msg + "]");
                }

                /**
                 * 当音区发生变化时收到回调，进房时也会有首次回调
                 *
                 * @param audioZone 音区ID
                 * @param streamId  音视频流ID
                 */
                @Override
                public void onAudioZoneChanged(int audioZone, String streamId) {
                    AcLog.d(TAG, "onAudioZoneChanged: audioZone = [" + audioZone + "], streamId = [" + streamId + "]");
                    ToastUtils.showShort("onAudioZoneChanged: audioZone = [" + audioZone + "], streamId = [" + streamId + "]");
                }
            });

            /**
             * void setMultiAudioFocusAppListener(MultiAudioFocusAppListener listener)
             * 设置多屏音频焦点应用监听器
             *
             * @param listener 多屏音频焦点应用监听器
             */
            mMultiMediaStreamService.setMultiAudioFocusAppListener(new MultiMediaStreamService.MultiAudioFocusAppListener() {
                /**
                 * 当获取屏幕音频焦点应用包名时收到此回调
                 *
                 * @param audioZone   音区ID
                 * @param code        状态码：0-查询成功；其他-查询失败
                 * @param streamId    音视频流ID
                 * @param packageName 音频焦点应用包名
                 * @param msg         错误信息
                 */
                @Override
                public void onResult(@IntRange(from = 0) int audioZone, int code, String streamId, String packageName, String msg) {
                    AcLog.d(TAG, "[onResult] audioZone: " + audioZone + ", code: " + code + ", streamId: " + streamId + ", packageName: " +packageName + ", msg: " + msg);
                    ToastUtils.showShort("[onResult] audioZone: " + audioZone + ", code: " + code + ", streamId: " + streamId + ", packageName: " +packageName + ", msg: " + msg);
                }

                /**
                 * 当某个音区的音频焦点发生变化时，收到此回调；当应用获取或丢失音频焦点时收到此回调
                 *
                 * @param audioZone   音区ID
                 * @param streamId    音视频流ID
                 * @param packageName 音频焦点应用包名
                 * @param eventType   0-丢失焦点；1-获取焦点
                 */
                @Override
                public void onAudioFocusAppChanged(@IntRange(from = 0) int audioZone, String streamId, String packageName, int eventType) {
                    AcLog.d(TAG, "onAudioFocusAppChanged: audioZone = [" + audioZone + "], streamId = [" + streamId + "], packageName = [" + packageName + "], eventType = [" + eventType + "]");
                    ToastUtils.showShort("onAudioFocusAppChanged: audioZone = [" + audioZone + "], streamId = [" + streamId + "], packageName = [" + packageName + "], eventType = [" + eventType + "]");
                }
            });

            /**
             * void setMultiFocusedWindowAppListener(MultiFocusedWindowAppListener listener)
             * 设置多屏焦点应用监听器
             *
             * @listener 多屏焦点应用监听器
             */
            mMultiMediaStreamService.setMultiFocusedWindowAppListener(new MultiMediaStreamService.MultiFocusedWindowAppListener() {
                /**
                 * 当获取屏幕当前焦点应用包名时会收到此回调
                 *
                 * @param streamId 音视频流ID
                 * @param code 0 -- 成功并返回应用包名
                 *             else -- 失败及其对应的错误码
                 * @param packageName 焦点应用包名
                 * @param msg 错误信息
                 */
                @Override
                public void onResult(@NonNull String streamId, int code, String packageName, String msg) {
                    AcLog.d(TAG, "onResult: streamId = [" + streamId + "], code = [" + code + "], packageName = [" + packageName + "], msg = [" + msg + "]");
                    ToastUtils.showShort("onResult: streamId = [" + streamId + "], code = [" + code + "], packageName = [" + packageName + "], msg = [" + msg + "]");
                }

                /**
                 * 当某个屏幕上焦点应用发生改变时收到此回调
                 *
                 * @param streamId 音视频流ID
                 * @param packageName 焦点应用包名
                 */
                @Override
                public void onFocusedWindowAppChanged(@NonNull String streamId, @NonNull String packageName) {
                    AcLog.d(TAG, "onFocusedWindowAppChanged: streamId = [" + streamId + "], packageName = [" + packageName + "]");
                    ToastUtils.showShort("onFocusedWindowAppChanged: streamId = [" + streamId + "], packageName = [" + packageName + "]");
                }
            });

            /**
             * void setMultiScreenStateListener(MultiScreenStateListener listener)
             * 设置全屏状态监听器，监听状态栏、导航栏可见性变化
             *
             * @param listener 全屏状态监听器
             */
            mMultiMediaStreamService.setMultiScreenStateListener(new MultiMediaStreamService.MultiScreenStateListener() {
                /**
                 * 当前台运行程序的全屏状态发生改变时收到此回调，应用切换但导航栏或状态栏开关状态没有变化时不会收到此回调
                 *
                 * @param streamId 音视频流ID
                 * @param screenState 音视频流ID对应屏幕的全屏状态
                 */
                @Override
                public void onScreenStateChanged(@NonNull String streamId, @NonNull MultiMediaStreamService.ScreenState screenState) {
                    AcLog.d(TAG, "onScreenStateChanged: streamId = [" + streamId + "], screenState = [" + screenState + "]");
                    ToastUtils.showShort("onScreenStateChanged: streamId = [" + streamId + "], screenState = [" + screenState + "]");
                }
            });

        }
    }

    /**
     * 即将废弃，建议使用{@link IPlayerListener#onServiceInit(Map)}
     */
    @Override
    public void onServiceInit() {
        AcLog.d(TAG, "[onServiceInit]");
    }

    @Override
    public void onFirstAudioFrame(String s) {
        AcLog.d(TAG, "[onFirstAudioFrame] audioStreamId: " + s);
    }

    @Override
    public void onFirstRemoteVideoFrame(String s) {
        AcLog.d(TAG, "[onFirstRemoteVideoFrame] videoStreamId: " + s);
    }

    @Override
    public void onStreamStarted() {
        AcLog.d(TAG, "[onStreamStarted]");
    }

    @Override
    public void onStreamPaused() {
        AcLog.d(TAG, "[onStreamPaused]");
    }

    @Override
    public void onStreamResumed() {
        AcLog.d(TAG, "[onStreamResumed]");
    }

    @Override
    public void onStreamStats(StreamStats streamStats) {
        AcLog.d(TAG, "[onStreamStats] streamStats: " + streamStats);
    }

    @Override
    public void onLocalStreamStats(LocalStreamStats localStreamStats) {
        AcLog.d(TAG, "[onLocalStreamStats] localStreamStats: " + localStreamStats);
    }

    @Override
    public void onStreamConnectionStateChanged(int i) {
        AcLog.d(TAG, "[onStreamConnectionStateChanged] connectionState: " + i);
    }

    @Override
    public void onDetectDelay(long l) {
        AcLog.d(TAG, "[onDetectDelay] detectDelay: " + l);
    }

    @Override
    public void onRotation(int i) {
        AcLog.d(TAG, "[onRotation] rotation: " + i);
        setRotation(i);
    }

    @Override
    public void onPodExit(int i, String s) {
        AcLog.d(TAG, "[onPodExit] errorCode: " + i + ", errorMsg: " + s);
    }

    @Override
    public void onNetworkQuality(int i) {
        AcLog.d(TAG, "[onNetworkQuality] quality: " + i);
    }

    private void setRotation(int rotation) {
        switch (rotation) {
            case 0:
            case 180:
                setRequestedOrientation(SCREEN_ORIENTATION_SENSOR_PORTRAIT);
                break;
            case 90:
            case 270:
                setRequestedOrientation(SCREEN_ORIENTATION_SENSOR_LANDSCAPE);
                break;
        }
    }

}
