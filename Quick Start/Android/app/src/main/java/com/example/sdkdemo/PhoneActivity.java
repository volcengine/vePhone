package com.example.sdkdemo;

import static android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE;
import static android.content.pm.ActivityInfo.SCREEN_ORIENTATION_SENSOR_PORTRAIT;

import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
import android.content.res.Configuration;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.ProgressBar;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

import com.volcengine.androidcloud.common.log.AcLog;
import com.volcengine.androidcloud.common.model.StreamStats;
import com.volcengine.cloudcore.common.mode.LocalStreamStats;
import com.volcengine.cloudphone.apiservice.IClipBoardListener;
import com.volcengine.cloudphone.apiservice.StreamProfileChangeCallBack;
import com.volcengine.cloudphone.apiservice.outinterface.IPlayerListener;
import com.volcengine.cloudphone.apiservice.outinterface.IStreamListener;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import java.text.MessageFormat;
import java.util.Locale;

public class PhoneActivity extends AppCompatActivity implements IPlayerListener, IStreamListener {

    private final String TAG = getClass().getSimpleName();
    private ViewGroup mContainer;
    private ProgressBar mProgressBar;
    public static final String KEY_POD_ID = "podId";

    public VePhoneEngine vePhoneEngine = VePhoneEngine.getInstance();

    public static void start(Activity activity) {
        Intent intent = new Intent(activity, PhoneActivity.class);
        activity.startActivity(intent);
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        setContentView(R.layout.activity_play);
        mContainer = findViewById(R.id.view_container);
        mProgressBar = findViewById(R.id.progress_bar);
        start();
    }

    private void start() {
        // 更多更具体的参数信息请参考：https://www.volcengine.com/docs/6394/75742#%E5%88%9D%E5%A7%8B%E5%8C%96
        PhonePlayConfig.Builder builder = new PhonePlayConfig.Builder();
        builder
                // 以下是必填参数
                .userId(MainActivity.getUid()) // 必填参数，自定义用户 userid
                .ak(MainActivity.getAk()) // 必填参数，申请云手机服务临时 ak
                .sk(MainActivity.getSk())  // 必填参数，申请云手机服务临时 sk
                .token(MainActivity.getToken()) // 必填参数，申请云手机服务临时 token
                .productId(MainActivity.getProductId()) // 必填参数，可通过火山引擎云手机控制台『业务管理』页面获取
                .podId(MainActivity.getPodId())
                .container(mContainer) //必填参数，用来承载画面的Container, 需要是FrameLayout或者FrameLayout的子类
                // 以下是选填参数，可以根据实际需求进行设置
//                .rotation(Rotation.PORTRAIT) //选填参数，您创建的pod的默认屏幕方向，正确填写该值有助于优化首帧闪动问题
//                .useCloudNative(true) //选填参数，使用云原生pod，从SDK v1.18.0开始支持此参数
//                .debugConfig(new JSONObject(){{  //选填参数，SDK开发调试配置项
//                    boolean cloudNative = true;
//                    try {
//                        put("Version", cloudNative ? "2022-08-01" : "2020-10-25");  //SDK v1.18.0之前通过此方式切换云原生
//                    } catch (JSONException e) {
//                        e.printStackTrace();
//                    }
//                }}.toString())
//                .roundId("123456") // 选填参数，自定义roundId
//                .videoStreamProfileId(12) // 选填参数，清晰度ID;
//                .appId("1459053923124908032")// 选填选项。打开指定应用，应用ID 请根据火山引擎控制台 - 控制台应用管理中获得
//                .displayList(new HashMap<String, VeDisplay>(){{  //选填参数，指定需要拉流的屏幕ID
//                    // 多屏pod场景，客户端设置需要拉流的屏幕，注意只能有一个mainScreen
//                    put("0-0", new VeDisplay.Builder().container(mContainer).mainScreen(true).build());
//                    put("0-1", new VeDisplay.Builder().container(mContainer2).mainScreen(false).build());
//                }})
                .streamListener(PhoneActivity.this);

        PhonePlayConfig phoneConfig = builder.build();
        vePhoneEngine.start(phoneConfig, PhoneActivity.this);
    }


    @Override
    protected void onResume() {
        super.onResume();
        // 恢复音视频拉流
        vePhoneEngine.resume();
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    @Override
    protected void onPause() {
        super.onPause();
        // 暂停音视频拉流
        vePhoneEngine.pause();
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    @Override
    protected void onDestroy() {
        // 销毁引擎回收资源
        vePhoneEngine.stop();
        super.onDestroy();
    }

    @Override
    public void onPlaySuccess(String roundId, int clarityId) {
        Log.d(TAG, "onPlaySuccess() called with: roundId = [" + roundId + "], clarityId = [" + clarityId + "]");
        mProgressBar.setVisibility(View.GONE);
    }

    @Override
    public void onError(int code, String msg) {
        Log.e(TAG, "onError() called with: code = [" + code + "], msg = [" + msg + "]");
        mProgressBar.setVisibility(View.GONE);
        showAlertDialog("启动错误", code, msg);
    }

    @Override
    public void onWarning(int code, String msg) {
        Log.w(TAG, "onWarning() called with: code = [" + code + "], msg = [" + msg + "]");
    }

    @Override
    public void onNetworkChanged(int networkType) {
        Log.d(TAG, "onNetworkChanged() called with: networkType = [" + networkType + "]");
    }

    @Override
    public void onServiceInit() {
        // 在onServiceInit回调中去获取服务并设置各种事件回调
        vePhoneEngine.getClarityService().setStreamProfileChangeListener(new StreamProfileChangeCallBack() {
            @Override
            public void onVideoStreamProfileChange(boolean isSuccess, int from, int to) {
                Log.d(TAG, "onVideoStreamProfileChange() called with: isSuccess = [" + isSuccess + "], from = [" + from + "], to = [" + to + "]");
            }

            @Override
            public void onError(int code, String msg) {
                Log.d(TAG, "VideoStreamProfileChange onError() called with: code = [" + code + "], msg = [" + msg + "]");
            }
        });
        vePhoneEngine.getClipBoardServiceManager().setBoardSyncClipListener(new IClipBoardListener() {
            @Override
            public void onClipBoardMessageReceived(ClipData clipData) {
                AcLog.d(TAG, " onClipBoardMessageReceived " + clipData.getItemAt(0).getText());
                Toast.makeText(PhoneActivity.this, clipData.getItemAt(0).getText(), Toast.LENGTH_SHORT).show();
            }
        });
    }

    @Override
    public void onFirstAudioFrame(String uid) {
        Log.d(TAG, "onFirstAudioFrame " + uid);
    }

    @Override
    public void onFirstRemoteVideoFrame(String uid) {
        Log.d(TAG, "onFirstRemoteVideoFrame " + uid);
    }

    @Override
    public void onStreamStarted() {
        Log.d(TAG, "onStreamStarted ");
    }

    @Override
    public void onStreamPaused() {
        Log.d(TAG, "onStreamPaused ");
    }

    @Override
    public void onStreamResumed() {
        Log.d(TAG, "onStreamResumed ");
    }

    @Override
    public void onStreamStats(StreamStats streamStats) {
        String stats = String.format(
                Locale.getDefault(),
                "Fps: %d, Video: %d kbps LossRate: %.2f, stallCount: %d, rtt : %d, StallDuration: %d, FrozenRate: %d",
                streamStats.getRendererOutputFrameRate(),
                streamStats.getReceivedVideoBitRate(),
                streamStats.getVideoLossRate(),
                streamStats.getStallCount(),
                streamStats.getRtt(),
                streamStats.getStallDuration(),
                streamStats.getFrozenRate()
        );
        AcLog.d(TAG, "onStreamStats: " + stats);
    }

    @Override
    public void onLocalStreamStats(LocalStreamStats localStreamStats) {

    }

    @Override
    public void onStreamConnectionStateChanged(int i) {
        Log.d(TAG, "onStreamConnectionStateChanged " + i);
    }

    @Override
    public void onConfigurationChanged(@NonNull Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        AcLog.d(TAG, "onConfigurationChanged newConfig " + newConfig);
        vePhoneEngine.rotate(newConfig.orientation);
    }

    @Override
    public void onDetectDelay(long l) {
        Log.d(TAG, "delay " + l);
    }

    @Override
    public void onRotation(int rotation) {
        Log.d(TAG, "onRotation() called with: rotation = [" + rotation + "]");
        // 客户端进入房间后，pod会通过此接口返回当前的屏幕方向，从而实现屏幕方向同步
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

    @Override
    public void onPodExit(int code, String msg) {
        Log.d(TAG, "onPodExit() called with: code = [" + code + "], msg = [" + msg + "]");
        showAlertDialog("pod异常退出", code, msg);
    }


    protected void showAlertDialog(String title, int code, String msg) {
        AlertDialog alertDialog = new AlertDialog.Builder(this)
                .setTitle(title)
                .setMessage(MessageFormat.format(
                        "code: {0}, msg: {1}\n{2}",
                        code, msg, vePhoneEngine.getDebugData()  //getDebugData可以获取调试信息用于快速定位问题
                ))
                .setPositiveButton("知道了", (dialog, which) -> {
                    dialog.dismiss();
                })
                .setNegativeButton("关闭页面", (dialog, which) -> {
                    dialog.dismiss();
                    finish();
                }).create();
        alertDialog.setCanceledOnTouchOutside(false);
        alertDialog.getWindow().setFlags(WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE, WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE);
        if (!isFinishing()) {
            alertDialog.show();
            alertDialog.getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LOW_PROFILE
                    | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_FULLSCREEN
                    | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                    | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                    | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                    | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION);
            alertDialog.getWindow().clearFlags(WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE);
        }
    }
}
