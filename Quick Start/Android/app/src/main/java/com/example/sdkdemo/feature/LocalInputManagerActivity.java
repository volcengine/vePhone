package com.example.sdkdemo.feature;

import android.content.res.Configuration;
import android.os.Bundle;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.EditText;
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
import com.volcengine.cloudphone.apiservice.LocalInputManager;
import com.volcengine.cloudphone.apiservice.outinterface.IPlayerListener;
import com.volcengine.cloudphone.apiservice.outinterface.IStreamListener;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import org.json.JSONException;
import org.json.JSONObject;

import java.util.Map;

/**
 * 该类用于展示与本地输入{@link LocalInputManager}相关的功能接口
 * 使用该服务可以使用本地输入法完成对云端实例中输入框的文字输入。
 */
public class LocalInputManagerActivity extends BasePlayActivity
        implements IPlayerListener, IStreamListener {

    private final String TAG = "LocalInputManagerActivity";

    private ViewGroup mContainer;
    private PhonePlayConfig mPhonePlayConfig;
    private PhonePlayConfig.Builder mBuilder;
    private LocalInputManager mLocalInputManager;
    private SwitchCompat mSwShowOrHide, mSwShowLocalData, mSwCloseLocalManager;
    private LinearLayoutCompat mLlButtons;
    private Button mBtnCoverCurrentEditTextMessage, mBtnSendInputText, mBtnGetTextInputEnable;
    EditText mEtTextInput;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        setContentView(R.layout.activity_local_input);
        initView();
        initPhonePlayConfig();
    }

    private void initView() {
        mContainer = findViewById(R.id.container);
        mSwShowOrHide = findViewById(R.id.sw_show_or_hide);
        mLlButtons = findViewById(R.id.ll_buttons);
        mEtTextInput = findViewById(R.id.et_text_input);
        mBtnCoverCurrentEditTextMessage = findViewById(R.id.btn_cover_current_edit_text_message);
        mBtnSendInputText = findViewById(R.id.btn_send_input_text);
        mBtnGetTextInputEnable = findViewById(R.id.btn_get_keyboard_status);
        mSwShowLocalData = findViewById(R.id.sw_show_local_data);
        mSwCloseLocalManager = findViewById(R.id.sw_close_input_manager);

        mSwShowOrHide.setOnCheckedChangeListener((buttonView, isChecked) -> {
            mLlButtons.setVisibility(isChecked ? View.VISIBLE : View.GONE);
        });

        /**
         * coverCurrentEditTextMessage(String text) -- 覆盖当前输入框的内容
         */
        mBtnCoverCurrentEditTextMessage.setOnClickListener(v -> {
            if (mLocalInputManager != null) {
                mLocalInputManager.coverCurrentEditTextMessage(mEtTextInput.getText().toString());
            }
            else {
                AcLog.e(TAG, "mLocalInputManager == null");
            }
        });

        /**
         * sendInputText(String text) -- 向当前输入框追加内容
         */
        mBtnSendInputText.setOnClickListener(v -> {
            if (mLocalInputManager != null) {
                mLocalInputManager.sendInputText(mEtTextInput.getText().toString());
            }
            else {
                AcLog.e(TAG, "mLocalInputManager == null");
            }
        });

        /**
         * enableShowCurrentInputText(boolean enable) -- 显示当前输入框内容
         */
        mSwShowLocalData.setChecked(false);
        mSwShowLocalData.setOnCheckedChangeListener((buttonView, isChecked) -> {
            if (mLocalInputManager != null) {
                mLocalInputManager.enableShowCurrentInputText(isChecked);
            }
            else {
                AcLog.e(TAG, "mLocalInputManager == null");
            }
        });

        /**
         * closeAutoKeyBoard(boolean isIntercept) -- 是否拦截SDK调起本地键盘
         *
         * @param isIntercept false -- 不拦截
         *                    true -- 拦截，由用户自行处理本地键盘的调起和内容的发送
         */
        mSwCloseLocalManager.setChecked(false);
        mSwCloseLocalManager.setOnCheckedChangeListener((buttonView, isChecked) -> {
            if (mLocalInputManager != null) {
                mLocalInputManager.closeAutoKeyBoard(isChecked);
            }
            else {
                AcLog.e(TAG, "mLocalInputManager == null");
            }
        });

        /**
         * 云端实例输入框是否支持发送文本
         * isTextInputEnable()
         *
         * @return 云端输入框可发送状态
         *         <li>true：可发送，此状态下允许调用{@link LocalInputManager#sendInputText(String)}接口向pod输入框发送文字</li>
         *         <li>false：不可发送</li>
         */
        mBtnGetTextInputEnable.setOnClickListener(v -> {
            if (mLocalInputManager != null) {
                showToast("" + mLocalInputManager.isTextInputEnable());
            }
            else {
                AcLog.e(TAG, "mLocalInputManager == null");
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
        mLocalInputManager = VePhoneEngine.getInstance().getLocalInputManager();
        if (mLocalInputManager != null) {
            mLocalInputManager.setRemoteInputCallBack(new LocalInputManager.RemoteInputCallBack() {
                /**
                 * 云端输入法准备阶段的一些状态回调
                 *
                 * @param hintText 提示文本
                 * @param inputType 输入格式
                 */
                @Override
                public void onPrepare(String hintText, int inputType) {
                    AcLog.i(TAG, "[onPrepare] hintText: " + hintText + ", inputType: " + inputType);
                }

                /**
                 * 云端输入法软键盘请求弹出的回调，该回调会触发多次
                 */
                @Override
                public void onCommandShow() {
                    AcLog.i(TAG, "[onCommandShow]");
                }

                /**
                 * 云端输入法软键盘请求收起的回调
                 */
                @Override
                public void onCommandHide() {
                    AcLog.i(TAG, "[onCommandHide]");
                }

                /**
                 * 云端输入框内容变化的回调
                 *
                 * @param text 输入框内容发生变化后的文本信息
                 */
                @Override
                public void onTextChange(String text) {
                    AcLog.i(TAG, "[onTextChange] text: " + text);
                }

                /**
                 * 不适用于云手机场景，可忽略
                 */
                @Override
                public void onRemoteKeyBoardEnabled(boolean enable) {

                }

                /**
                 * 云端实例输入框是否支持发送文本状态变化回调
                 *
                 * @param enable true -- 支持
                 *               false -- 不支持
                 */
                @Override
                public void onTextInputEnableStateChanged(boolean enable) {
                    AcLog.i(TAG, "[onTextInputEnableStateChanged] enable: " + enable);
                }
            });
        }
        else {
            AcLog.e(TAG, "mLocalInputManager == null");
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
