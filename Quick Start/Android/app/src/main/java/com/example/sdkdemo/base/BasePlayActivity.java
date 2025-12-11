package com.example.sdkdemo.base;


import android.app.AlertDialog;
import android.content.DialogInterface;
import android.content.pm.ActivityInfo;
import android.content.res.Configuration;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;

import com.example.sdkdemo.R;
import com.example.sdkdemo.feature.MessageChannelActivity;
import com.volcengine.androidcloud.common.model.RotationState;
import com.volcengine.androidcloud.common.model.StreamStats;
import com.volcengine.androidcloud.common.pod.Rotation;
import com.volcengine.cloudcore.common.mode.LocalStreamStats;
import com.volcengine.cloudcore.common.mode.StreamIndex;
import com.volcengine.cloudcore.common.mode.StreamType;
import com.volcengine.cloudphone.apiservice.outinterface.IPlayerListener;
import com.volcengine.cloudphone.apiservice.outinterface.IStreamListener;
import com.volcengine.common.SDKContext;
import com.volcengine.phone.VePhoneEngine;

import java.text.MessageFormat;
import java.util.Map;

public class BasePlayActivity extends AppCompatActivity implements IPlayerListener, IStreamListener {
    public final String TAG;
    {
        TAG = getClass().getSimpleName();
    }
    private long lastBackPress;

    @Override
    public void onConfigurationChanged(@NonNull Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        Log.d(TAG, "[onConfigurationChanged] newConfig: " + newConfig.orientation);
        VePhoneEngine.getInstance().rotate(newConfig.orientation);
    }

    /**
     * 调整Activity的显示方向
     *
     * @param rotation 旋转方向
     *                 0/180  -- 将Activity调整为竖屏显示
     *                 90/270 -- 将Activity调整为横屏显示
     */
    protected void setRotation(int rotation) {
        switch (rotation) {
            case 0:
            case 180:
                setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_SENSOR_PORTRAIT);
                break;
            case 90:
            case 270:
                setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE);
                break;
        }
    }

    @Override
    public void onBackPressed() {
        long current = System.currentTimeMillis();
        if (current - lastBackPress < 1000L) {
            super.onBackPressed();
        } else {
            Toast.makeText(this, getString(R.string.back_again_to_exit), Toast.LENGTH_SHORT).show();
            lastBackPress = current;
        }
    }

    protected void showToast(String s) {
        Toast.makeText(this, s, Toast.LENGTH_SHORT).show();
    }

    /**
     * 播放成功回调
     *
     * @param roundId 当次会话生命周期标识符
     * @param clarityId 当前画面的清晰度，首帧渲染到画面时触发该回调
     */
    @Override
    public void onPlaySuccess(String roundId, int clarityId) {
        Log.d(TAG, "[onPlaySuccess] roundId " + roundId + " clarityId " + clarityId);
    }

    /**
     * SDK内部产生的错误回调
     *
     * @param code 错误码
     * @param msg 错误详情
     */
    @Override
    public void onError(int code, String msg) {
        Log.e(TAG, "[onError] code: " + code + ", msg: " + msg);
        toggleLoadingUI(false);
        showTipDialog("启动拉流失败，错误原因：\n" + MessageFormat.format("code:{0}\nmsg:{1}", String.valueOf(code), msg));
    }

    /**
     * SDK内部产生的警告回调
     *
     * @param code 警告码
     * @param msg 警告详情
     */
    @Override
    public void onWarning(int code, String msg) {
        Log.d(TAG, "[onWarning] code: " + code + ", msg: " + msg);
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
        Log.d(TAG, "[onNetworkChanged] networkType: " + networkType);
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
        Log.d(TAG, "[onServiceInit] extras: " + extras);
    }

    /**
     * 客户端加房成功并收到对端发布视频流时触发，收到此回调后业务方可以对串流进行订阅和退订操作
     *
     * @param index 串流索引，保留参数，当前仅会返回{@link StreamIndex#MAIN}
     * @param type 串流类型
     */
    @Override
    public void onStreamReady(@StreamIndex int index, StreamType type) {
        Log.d(TAG, "onStreamReady: index:" + index + ", type:" + type);
    }

    /**
     * 收到音频首帧时的回调
     *
     * @param uid 远端实例音频流的ID
     */
    @Override
    public void onFirstAudioFrame(String uid) {
        Log.d(TAG, "[onFirstAudioFrame] uid: " + uid);
    }

    /**
     * 收到视频首帧时的回调
     *
     * @param uid 远端实例视频流的ID
     */
    @Override
    public void onFirstRemoteVideoFrame(String uid) {
        Log.d(TAG, "[onFirstRemoteVideoFrame] uid: " + uid);
        toggleLoadingUI(false);
    }

    /**
     * 开始播放的回调
     */
    @Override
    public void onStreamStarted() {
        Log.d(TAG, "[onStreamStarted]");
    }

    /**
     * 暂停播放后的回调，调用{@link VePhoneEngine#pause()}后会触发
     */
    @Override
    public void onStreamPaused() {
        Log.d(TAG, "[onStreamPaused]");
    }

    /**
     * 恢复播放后的回调，调用{@link VePhoneEngine#resume()} 或 VePhoneEngine#muteAudio(false) 后会触发
     */
    @Override
    public void onStreamResumed() {
        Log.d(TAG, "[onStreamResumed]");
    }

    /**
     * 周期为2秒的音视频网络状态的回调，可用于内部数据分析或监控
     *
     * @param stats 远端视频流的性能状态
     */
    @Override
    public void onStreamStats(StreamStats stats) {
        Log.d(TAG, "[onStreamStats] stats: " + stats);
    }

    /**
     * 周期为2秒的本地推送的音视频流的状态回调
     *
     * @param stats 本地音视频流的性能状态
     */
    @Override
    public void onLocalStreamStats(LocalStreamStats stats) {
        Log.d(TAG, "[onLocalStreamStats] stats: " + stats);
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
        Log.d(TAG, "[onStreamConnectionStateChanged] connectionState: " + state);
    }

    /**
     * 操作延迟回调
     *
     * @param elapse 操作延迟的具体值，单位:毫秒
     */
    @Override
    public void onDetectDelay(long elapse) {
        Log.d(TAG, "[onDetectDelay] detectDelay: " + elapse);
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
     * @param state pod当前的旋转状态，含旋转方向、旋转模式等
     *          0, 180 -- 竖屏
     *         90, 270 -- 横屏
     */
    @Override
    public void onRotation(@NonNull RotationState state) {
        Log.d(TAG, "[onRotation]: " + state.rotation + ", mode:" + state.mode);
        if (state.mode == Rotation.AUTO_ROTATION) {
            // 自动旋转模式：对应启动时{builder.rotation(Rotation.AUTO_ROTATION)}
            setRotation(state.rotation);
            // 解决横屏状态下container方向不对的问题
            VePhoneEngine.getInstance().rotate(Rotation.from(state.rotation).orientation);
        } else {
            // 穿透模式：对应启动时{builder.rotation(Rotation.PORTRAIT)}，不推荐用穿透模式，已废弃
            // 推荐使用SDK内部旋转方案，参考：{builder.videoRotationMode()}及{RotationModeActivity}
            Rotation displayRotation = SDKContext.getDisplayRotation();
            if (state.mode != displayRotation) {
                setRotation(state.mode.toRotation());
                VePhoneEngine.getInstance().rotate(Rotation.from(state.rotation).orientation);
            }
        }
    }


    /**
     * 远端实例退出回调
     *
     * @param code 退出的原因码
     * @param msg 退出的原因详情
     */
    @Override
    public void onPodExit(int code, String msg) {
        Log.d(TAG, "[onPodExit] code: " + code + ", msg: " + msg);
        showTipDialog("Pod退出房间拉流断开，请重试：\n" + MessageFormat.format("code:{0}\nmsg:{1}", String.valueOf(code), msg));
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
        Log.d(TAG, "[onNetworkQuality] quality: " + quality);
    }


    protected void showTipDialog(String message) {
        new AlertDialog.Builder(this)
                .setCancelable(false)
                .setTitle("提示")
                .setMessage(message)
                .setPositiveButton("OK", new DialogInterface.OnClickListener() {
                    @Override
                    public void onClick(DialogInterface dialog, int which) {
                        finish();
                    }
                })
                .show();
    }

    private View loadingUI;

    private void toggleLoadingUI(boolean visible) {
        if (loadingUI == null) {
            loadingUI = findViewById(R.id.progress_bar);
        }
        loadingUI.setVisibility(visible ? View.VISIBLE : View.GONE);
    }
}
