package com.example.sdkdemo.feature;

import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.widget.LinearLayoutCompat;
import androidx.appcompat.widget.SwitchCompat;

import com.example.sdkdemo.R;
import com.example.sdkdemo.util.ScreenUtil;
import com.example.sdkdemo.base.BasePlayActivity;
import com.example.sdkdemo.util.SdkUtil;
import com.volcengine.cloudphone.apiservice.IMessageChannel;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import java.util.Map;

/**
 * 该类用于展示与消息通道{@link IMessageChannel}相关的功能接口
 * 使用该服务可以实现本地与云端实例的消息通信。
 */
public class MessageChannelActivity extends BasePlayActivity {

    private FrameLayout mContainer;
    private IMessageChannel mMessageChannel;
    private SwitchCompat mSwShowOrHide;
    private LinearLayoutCompat mLlButtons;
    private Button mBtnAckMsg, mBtnUidAckMsg, mBtnTimeoutMsg, mBtnUidTimeoutMsg;


    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        setContentView(R.layout.activity_message_channel);
        initView();
        initPlayConfigAndStartPlay();
    }

    private void initView() {
        mContainer = findViewById(R.id.container);
        mSwShowOrHide = findViewById(R.id.sw_show_or_hide);
        mLlButtons = findViewById(R.id.ll_buttons);
        mBtnAckMsg = findViewById(R.id.btn_ack_msg);
        mBtnUidAckMsg = findViewById(R.id.btn_uid_ack_msg);
        mBtnTimeoutMsg = findViewById(R.id.btn_timeout_msg);
        mBtnUidTimeoutMsg = findViewById(R.id.btn_uid_timeout_msg);

        mSwShowOrHide.setOnCheckedChangeListener((buttonView, isChecked) -> {
            mLlButtons.setVisibility(isChecked ? View.VISIBLE : View.GONE);
        });

        String channelUid = "com.bytedance.vemessagechannelprj.prj1";
        mBtnAckMsg.setOnClickListener(v -> {
            if (mMessageChannel != null) {
                /**
                 * 发送回执消息到云端应用(当云端只有一个应用注册消息通道时使用)
                 *
                 * @param payload 发送内容，size：60KB
                 * @param needAck 是否需要云端Ack回执
                 * @return 消息实体
                 */
                IMessageChannel.IChannelMessage ackMsg =
                        mMessageChannel.sendMessage("ackMsg", true);
                Log.i(TAG, "ackMsg: " + ackMsg);
            }
            else {
                Log.e(TAG, "mMessageChannel == null");
            }
        });
        mBtnUidAckMsg.setOnClickListener(v -> {
            if (mMessageChannel != null) {
                /**
                 * 发送回执消息到云端应用(当云端有多个应用注册消息通道时使用，需要指定目标用户ID，即应用包名)
                 *
                 * @param payload        发送内容，size：60KB
                 * @param needAck        是否需要云端Ack回执
                 * @param destChannelUid 目标用户消息通道ID
                 * @return 消息实体
                 */
                IMessageChannel.IChannelMessage uidAckMsg =
                        mMessageChannel.sendMessage("uidAckMsg", true, channelUid);
                Log.i(TAG, "uidAckMsg: " + uidAckMsg);
            }
            else {
                Log.e(TAG, "mMessageChannel == null");
            }
        });
        mBtnTimeoutMsg.setOnClickListener(v -> {
            if (mMessageChannel != null) {
                /**
                 * 发送超时消息到云端应用(当云端只有一个应用注册消息通道时使用)
                 *
                 * @param payload 发送内容，size：60KB
                 * @param timeout 消息超时时长，单位：ms，需要大于0；当小于等于0时，通过
                 *                  {@link com.volcengine.cloudphone.apiservice.IMessageChannel.IMessageReceiver#onError(int, String)}
                 *                  返回错误信息
                 * @return 消息实体
                 */
                IMessageChannel.IChannelMessage timeoutMsg =
                        mMessageChannel.sendMessage("timeoutMsg", 3000);
                Log.i(TAG, "timeoutMsg: " + timeoutMsg);
            }
            else {
                Log.e(TAG, "mMessageChannel == null");
            }
        });
        mBtnUidTimeoutMsg.setOnClickListener(v -> {
            if (mMessageChannel != null) {
                /**
                 * 发送超时消息到云端应用(当云端有多个应用注册消息通道时使用，需要指定目标用户ID，即应用包名)
                 *
                 * @param payload        发送内容，size：60KB
                 * @param timeout        消息超时时长，单位：ms，需要大于0；当小于等于0时，通过
                 *                         {@link com.volcengine.cloudphone.apiservice.IMessageChannel.IMessageReceiver#onError(int, String)}
                 *                         返回错误信息
                 * @param destChannelUid 目标用户消息通道ID
                 * @return 消息实体
                 */
                IMessageChannel.IChannelMessage uidTimeoutMsg =
                        mMessageChannel.sendMessage("uidTimeoutMsg", 3000, channelUid);
                Log.i(TAG, "uidTimeoutMsg: " + uidTimeoutMsg);
            }
            else {
                Log.e(TAG, "mMessageChannel == null");
            }
        });
    }

    private void initPlayConfigAndStartPlay() {
        SdkUtil.PlayAuth auth = SdkUtil.getPlayAuth(this);
        String roundId = "roundId_123";
        PhonePlayConfig.Builder builder = new PhonePlayConfig.Builder();
        builder.userId(SdkUtil.getClientUid())
                .ak(auth.ak)
                .sk(auth.sk)
                .token(auth.token)
                .container(mContainer)
                .enableLocalKeyboard(true)
                .roundId(roundId)
                .podId(auth.podId)
                .productId(auth.productId)
                .streamListener(this);
        VePhoneEngine.getInstance().start(builder.build(), this);
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
        mMessageChannel = VePhoneEngine.getInstance().getMessageChannel();
        if (mMessageChannel != null) {
            /**
             * 设置消息接收回调监听
             *
             * @param listener 消息接收回调监听器
             */
            mMessageChannel.setMessageListener(new IMessageChannel.IMessageReceiver() {
                /**
                 * 消息接收回调
                 *
                 * @param iChannelMessage 接收的消息实体
                 */
                @Override
                public void onReceiveMessage(IMessageChannel.IChannelMessage iChannelMessage) {
                    Log.i(TAG, "[onReceiveMessage] message: " + iChannelMessage);
                    Toast.makeText(MessageChannelActivity.this, "[onReceiveMessage] message: " + iChannelMessage, Toast.LENGTH_SHORT).show();
                }

                @Override
                public void onReceiveBinaryMessage(IMessageChannel.IChannelBinaryMessage iChannelBinaryMessage) {
                    Log.d(TAG, "onReceiveBinaryMessage: ");
                }

                /**
                 * 发送消息结果回调
                 *
                 * @param success 是否发送成功
                 * @param messageId 消息ID
                 */
                @Override
                public void onSentResult(boolean success, String messageId) {
                    Log.i(TAG, "[onSentResult] success: " + success + ", messageId: " + messageId);
                    Toast.makeText(MessageChannelActivity.this, "[onSentResult] success: " + success + ", messageId: " + messageId, Toast.LENGTH_SHORT).show();
                }

                /**
                 * 已弃用，可忽略
                 */
                @Override
                public void ready() {
                    Log.i(TAG, "[ready]");
                }

                /**
                 * 错误信息回调
                 *
                 * @param errorCode 错误码
                 * @param errorMessage 错误信息
                 */
                @Override
                public void onError(int errorCode, String errorMessage) {
                    Log.i(TAG, "[onError] errorCode: " + errorCode + ", errorMessage: " + errorMessage);
                    Toast.makeText(MessageChannelActivity.this, "[onError] errorCode: " + errorCode + ", errorMessage: " + errorMessage, Toast.LENGTH_SHORT).show();
                }

                /**
                 * 云端游戏在线回调，建议在发送消息前监听该回调检查通道是否已连接
                 *
                 * @param channelUid 云端游戏的用户ID
                 */
                @Override
                public void onRemoteOnline(String channelUid) {
                    Log.i(TAG, "[onRemoteOnline] channelUid: " + channelUid);
                    Toast.makeText(MessageChannelActivity.this, "[onRemoteOnline] channelUid: " + channelUid, Toast.LENGTH_SHORT).show();
                }

                /**
                 * 云端游戏离线回调
                 *
                 * @param channelUid 云端游戏的用户ID
                 */
                @Override
                public void onRemoteOffline(String channelUid) {
                    Log.i(TAG, "[onRemoteOffline] channelUid: " + channelUid);
                    Toast.makeText(MessageChannelActivity.this, "[onRemoteOffline] channelUid: " + channelUid, Toast.LENGTH_SHORT).show();
                }
            });
        }
        else {
            Log.e(TAG, "mMessageChannel == null");
        }
    }

}
