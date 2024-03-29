package com.example.sdkdemo.feature;

import android.content.res.Configuration;
import android.os.Bundle;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.CompoundButton;
import android.widget.FrameLayout;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.widget.LinearLayoutCompat;
import androidx.appcompat.widget.SwitchCompat;

import com.example.sdkdemo.R;
import com.example.sdkdemo.util.ScreenUtil;
import com.example.sdkdemo.base.BasePlayActivity;
import com.example.sdkdemo.util.AssetsUtil;
import com.volcengine.androidcloud.common.log.AcLog;
import com.volcengine.androidcloud.common.model.StreamStats;
import com.volcengine.cloudcore.common.mode.LocalStreamStats;
import com.volcengine.cloudphone.apiservice.PodControlService;
import com.volcengine.cloudphone.apiservice.outinterface.IPlayerListener;
import com.volcengine.cloudphone.apiservice.outinterface.IStreamListener;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import org.json.JSONException;
import org.json.JSONObject;

import java.util.Map;

/**
 * 该类用于展示与实例控制{@link PodControlService}相关的功能接口的使用方法
 * 使用该服务可以对云端实例进行控制，其中包括设置无操作回收时长、截图、录屏、
 * 获取屏幕当前焦点应用、控制底部导航栏的显示与隐藏等等。
 */
public class PodControlServiceActivity extends BasePlayActivity
        implements IPlayerListener, IStreamListener {

    private final String TAG = "PodControlServiceActivity";

    private FrameLayout mContainer;
    private PhonePlayConfig mPhonePlayConfig;
    private PhonePlayConfig.Builder mBuilder;
    private PodControlService mPodControlService;
    private SwitchCompat mSwShowOrHide, mSwShowOrHideNavBar;
    private Button mBtnSwitchBackground, mBtnSwitchForeground, mBtnSetIdleTime,
            mBtnGetAutoRecycleTime, mBtnSetAutoRecycleTime, mBtnScreenShot, mBtnScreenRecord,
            mBtnGetFocusedWindowApp;
    private LinearLayoutCompat mLlButtons;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        setContentView(R.layout.activity_pod_control);
        initView();
        initPhonePlayConfig();
    }

    private void initView() {
        mContainer = findViewById(R.id.container);
        mSwShowOrHide = findViewById(R.id.sw_show_or_hide);
        mLlButtons = findViewById(R.id.ll_buttons);
        mBtnSwitchBackground = findViewById(R.id.btn_switch_background);
        mBtnSwitchForeground = findViewById(R.id.btn_switch_foreground);
        mBtnSetIdleTime = findViewById(R.id.btn_set_idle_time);
        mBtnGetAutoRecycleTime = findViewById(R.id.btn_get_auto_recycle_time);
        mBtnSetAutoRecycleTime = findViewById(R.id.btn_set_auto_recycle_time);
        mBtnScreenShot = findViewById(R.id.btn_screen_shot);
        mBtnScreenRecord = findViewById(R.id.btn_screen_record);
        mBtnGetFocusedWindowApp = findViewById(R.id.btn_get_focused_window_app);
        mSwShowOrHideNavBar = findViewById(R.id.sw_show_or_hide_nav_bar);

        mSwShowOrHide.setOnCheckedChangeListener((buttonView, isChecked) -> {
            mLlButtons.setVisibility(isChecked ? View.VISIBLE : View.GONE);
        });

        /**
         * 设置客户端应用切换前后台的状态
         * int switchBackground(boolean on)
         *
         * @param on true -- 切后台
         *           false -- 切前台
         * @return 0 -- 调用成功
         *         < 0 -- 调用失败
         */
        mBtnSwitchBackground.setOnClickListener(view -> {
            if (mPodControlService != null) {
                mPodControlService.switchBackground(true);
            }
            else {
                AcLog.e(TAG, "mPodControlService == null");
            }
        });
        mBtnSwitchForeground.setOnClickListener(view -> {
            if (mPodControlService != null) {
                mPodControlService.switchBackground(false);
            }
            else {
                AcLog.e(TAG, "mPodControlService == null");
            }
        });

        /**
         * 设置客户端切后台之后，云端实例的保活时间
         * int setIdleTime(long time)
         *
         * @param time 保活时长，单位秒
         *
         * @return 0 -- 调用成功
         *         < 0 -- 调用失败
         */
        mBtnSetIdleTime.setOnClickListener(v -> {
            if (mPodControlService != null) {
                int idleTime = 10;
                mPodControlService.setIdleTime(idleTime);
            }
            else {
                AcLog.e(TAG, "mPodControlService == null");
            }
        });

        /**
         * 设置无操作回收服务时长
         * int setAutoRecycleTime(int time, SetAutoRecycleTimeCallback callback)
         *
         * @param time 无操作回收服务时长，单位秒
         * @param callback 设置无操作回收服务时长的回调
         *
         * @return 0 -- 调用成功
         *         < 0 -- 调用失败
         */
        mBtnSetAutoRecycleTime.setOnClickListener(v -> {
            if (mPodControlService != null) {
                int autoRecycleTime = 20;
                mPodControlService.setAutoRecycleTime(autoRecycleTime, new PodControlService.SetAutoRecycleTimeCallback() {
                    @Override
                    public void onResult(int result, long time) {
                        showToast("[setAutoRecycleTimeResult] result: " + result + ", time: " + time);
                    }
                });
            }
            else {
                AcLog.e(TAG, "mPodControlService == null");
            }
        });

        /**
         * 查询无操作回收服务时长
         * int getAutoRecycleTime(GetAutoRecycleTimeCallback callback)
         *
         * @param callback 查询无操作回收服务时长的回调
         * @return 0 -- 调用成功
         *         < 0 -- 调用失败
         */
        mBtnGetAutoRecycleTime.setOnClickListener(v -> {
            if (mPodControlService != null) {
                mPodControlService.getAutoRecycleTime(new PodControlService.GetAutoRecycleTimeCallback() {
                    @Override
                    public void onResult(int result, long time) {
                        showToast("[getAutoRecycleTimeResult] result: " + result + ", time: " + time);
                    }
                });
            }
            else {
                AcLog.e(TAG, "mPodControlService == null");
            }
        });

        /**
         * 云手机截图，结果通过{@link PodControlService.ScreenShotListener#onScreenShot(int, String, String, String)}返回
         * int screenShot(boolean saveOnPod)
         *
         * @param saveOnPod 是否保存到pod本地，默认关闭
         *
         * @return 0 -- 调用成功
         *         < 0 -- 调用失败
         */
        mBtnScreenShot.setOnClickListener(v -> {
            if (mPodControlService != null) {
                mPodControlService.screenShot(true);
            }
            else {
                AcLog.e(TAG, "mPodControlService == null");
            }
        });

        /**
         * 云手机开启录屏，结果通过{@link PodControlService.ScreenRecordListener#onRecordingStatus(int, String, String, String)}返回
         * int startRecording(int duration, boolean saveOnPod)
         *
         * @param duration 录制时长，单位：秒
         * @param saveOnPod 是否保存到pod本地，默认关闭
         *
         * @return 0 -- 调用成功
         *         < 0 -- 调用失败
         */
        mBtnScreenRecord.setOnClickListener(v -> {
            if (mPodControlService != null) {
                mPodControlService.startRecording(10, true);
            }
            else {
                AcLog.e(TAG, "mPodControlService == null");
            }
        });

        /**
         * 获取屏幕当前焦点应用包名，结果通过{@link PodControlService.FocusedWindowAppListener#onResult(int, String, String)}接口返回
         * void getFocusedWindowApp()
         *
         * @return 0 -- 调用成功
         *         < 0 -- 调用失败
         */
        mBtnGetFocusedWindowApp.setOnClickListener(v -> {
            if (mPodControlService != null) {
                mPodControlService.getFocusedWindowApp();
            }
            else {
                AcLog.e(TAG, "mPodControlService == null");
            }
        });

        /**
         * 设置导航栏的状态
         * int setNavBarStatus(int status)
         *
         * 其中，打开导航栏的行为如下：
         * Launcher和非全屏应用会显示导航栏；
         * 申请全面屏应用导航栏自动隐藏。
         *
         * @param status 0 -- 隐藏导航栏
         *               1 -- 显示导航栏
         *
         * @return 0 -- 调用成功
         *         < 0 -- 调用失败
         */
        mSwShowOrHideNavBar.setOnCheckedChangeListener(new CompoundButton.OnCheckedChangeListener() {
            @Override
            public void onCheckedChanged(CompoundButton buttonView, boolean isChecked) {
                mPodControlService.setNavBarStatus(isChecked ?
                        PodControlService.NAV_BAR_STATUS_SHOW : PodControlService.NAV_BAR_STATUS_HIDDEN);
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
        mPodControlService = VePhoneEngine.getInstance().getPodControlService();
        if (mPodControlService != null) {
            /**
             * 设置云端应用切换前后台监听器
             * void setBackgroundSwitchListener(BackgroundSwitchListener listener)
             */
            mPodControlService.setBackgroundSwitchListener(new PodControlService.BackgroundSwitchListener() {
                /**
                 * 云端应用切换前后台的回调
                 *
                 * @param on true -- 切换到后台
                 *          false -- 切换到前台
                 */
                @Override
                public void onBackgroundSwitched(boolean on) {
                    AcLog.d(TAG, "[onBackgroundSwitched] isBackground: " + on);
                    showToast("[onBackgroundSwitched] isBackground: " + on);
                }
            });

            /**
             * 设置获取屏幕当前焦点应用包名监听器
             * void setFocusedWindowAppListener(FocusedWindowAppListener listener)
             */
            mPodControlService.setFocusedWindowAppListener(new PodControlService.FocusedWindowAppListener() {
                /**
                 * 获取屏幕当前焦点应用包名回调
                 *
                 * @param code 0 -- 成功并返回应用包名
                 *             else -- 失败错误码
                 * @param packageName 应用包名
                 * @param message     错误信息
                 */
                @Override
                public void onResult(int code, String packageName, String message) {
                    AcLog.i(TAG, "[onResult] code: " + code + ", packageName: " + packageName + ", message: " + message);
                }

                /**
                 * 当焦点窗口应用名称发生变化时回调。如果仅应用内activity窗口发生变化，但是应用包名未变化则不回调。
                 *
                 * @param packageName 应用包名
                 */
                @Override
                public void onFocusedWindowAppChanged(String packageName) {
                    AcLog.i(TAG, "[onFocusedWindowAppChanged] packageName: " + packageName);
                }
            });

            mPodControlService.setNavBarStatusChangeListener(new PodControlService.NavBarStatusChangeListener() {
                /**
                 * 改变导航栏状态回调
                 * 调用{@link PodControlService#getNavBarStatus()}方法、
                 * 调用{@link PodControlService#setNavBarStatus(int)}方法
                 * 都会触发该回调的执行。
                 *
                 * 回调执行时，通过入参reason区分调用来源。
                 *
                 * @param status 0 -- 隐藏导航栏
                 *               1 -- 显示导航栏
                 *               -1 -- 无效状态
                 * @param reason 回调原因(来源)
                 *               0 -- pod端切换发送回调
                 *               1 -- sdk调用{@link PodControlService#getNavBarStatus()}方法的回调
                 *               2 -- sdk调用{@link PodControlService#setNavBarStatus(int)}方法的回调
                 *               -1 -- sdk参数错误
                 */
                @Override
                public void onNavBarStatus(int status, int reason) {
                    AcLog.i(TAG, "[onNavBarStatus] status: " + status + " , reason: " + reason);
                }
            });

            mPodControlService.setScreenRecordListener(new PodControlService.ScreenRecordListener() {
                /**
                 * 录制状态回调
                 *
                 * @param status      录制状态：
                 *                    0 -- 录制成功，正常结束，上传TOS成功，返回录像文件保存路径
                 *                    1 -- 录制成功，正常结束，Pod本地端保存成功
                 *                    2 -- 开始录制成功
                 *                    3 -- 开始录制失败，正在录制中时调用了开始录制
                 *                    4 -- 结束录制失败，没有录制中的任务
                 *                    5 -- 录制失败，云手机存储空间不足，已占用存储空间总量的80%
                 *                    6 -- 录制结束，达到录制时限，返回录像文件保存路径
                 *                    7 -- 开始录制失败，录制时长超过上限
                 * @param savePath    完整保存路径
                 * @param downloadUrl 录屏文件的下载链接
                 * @param message     提示信息
                 */
                @Override
                public void onRecordingStatus(int status, String savePath, String downloadUrl, String message) {
                    AcLog.i(TAG, "[onRecordingStatus] status: " + status + ", savePath: " + savePath
                            + ", downloadUrl: " + downloadUrl + ", message: " + message);
                }
            });

            mPodControlService.setScreenShotListener(new PodControlService.ScreenShotListener() {
                /**
                 * 截图回调
                 *
                 * @param code        0 -- 成功并已保存
                 *                    else -- 失败错误码
                 * @param savePath    成功时返回文件在pod端的完整存放路径
                 * @param downloadUrl 图片的下载路径
                 * @param message     提示信息
                 */
                @Override
                public void onScreenShot(int code, String savePath, String downloadUrl, String message) {
                    AcLog.i(TAG, "[onScreenShot] code: " + code + ", savePath: " + savePath
                            + ", downloadUrl: " + downloadUrl + ", message: " + message);
                }
            });
        }
        else {
            AcLog.e(TAG, "mPodControlService == null");
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
}
