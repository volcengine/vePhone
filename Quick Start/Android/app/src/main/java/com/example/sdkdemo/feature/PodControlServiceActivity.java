package com.example.sdkdemo.feature;

import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.CompoundButton;
import android.widget.FrameLayout;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.widget.LinearLayoutCompat;
import androidx.appcompat.widget.SwitchCompat;

import com.example.sdkdemo.R;
import com.example.sdkdemo.util.ScreenUtil;
import com.example.sdkdemo.base.BasePlayActivity;
import com.example.sdkdemo.util.SdkUtil;
import com.volcengine.cloudphone.apiservice.PodControlService;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import java.text.MessageFormat;
import java.util.Map;

/**
 * 该类用于展示与实例控制{@link PodControlService}相关的功能接口的使用方法
 * 使用该服务可以对云端实例进行控制，其中包括设置无操作回收时长、截图、录屏、
 * 获取屏幕当前焦点应用、控制底部导航栏的显示与隐藏等等。
 */
public class PodControlServiceActivity extends BasePlayActivity {

    private FrameLayout mContainer;
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
        initPlayConfigAndStartPlay();
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
                Log.e(TAG, "mPodControlService == null");
            }
        });
        mBtnSwitchForeground.setOnClickListener(view -> {
            if (mPodControlService != null) {
                mPodControlService.switchBackground(false);
            }
            else {
                Log.e(TAG, "mPodControlService == null");
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
                Log.e(TAG, "mPodControlService == null");
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
                Log.e(TAG, "mPodControlService == null");
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
                Log.e(TAG, "mPodControlService == null");
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
                Log.e(TAG, "mPodControlService == null");
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
                Log.e(TAG, "mPodControlService == null");
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
                Log.e(TAG, "mPodControlService == null");
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
                            .roundId(SdkUtil.getRoundId())
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
    }

    @Override
    public void finish() {
        VePhoneEngine.getInstance().stop();
        super.finish();
    }

    @Override
    public void onServiceInit(@NonNull Map<String, Object> extras) {
        super.onServiceInit(extras);
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
                    Log.d(TAG, "[onBackgroundSwitched] isBackground: " + on);
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
                    Log.i(TAG, "[onResult] code: " + code + ", packageName: " + packageName + ", message: " + message);
                }

                /**
                 * 当焦点窗口应用名称发生变化时回调。如果仅应用内activity窗口发生变化，但是应用包名未变化则不回调。
                 *
                 * @param packageName 应用包名
                 */
                @Override
                public void onFocusedWindowAppChanged(String packageName) {
                    Log.i(TAG, "[onFocusedWindowAppChanged] packageName: " + packageName);
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
                    Log.i(TAG, "[onNavBarStatus] status: " + status + " , reason: " + reason);
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
                    Log.i(TAG, "[onRecordingStatus] status: " + status + ", savePath: " + savePath
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
                    Log.i(TAG, "[onScreenShot] code: " + code + ", savePath: " + savePath
                            + ", downloadUrl: " + downloadUrl + ", message: " + message);
                }
            });
        }
        else {
            Log.e(TAG, "mPodControlService == null");
        }
    }

}
