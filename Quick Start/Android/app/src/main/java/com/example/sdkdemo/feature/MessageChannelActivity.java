package com.example.sdkdemo.feature;

import android.os.Bundle;
import android.text.TextUtils;
import android.util.Log;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.TextView;

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

import java.text.MessageFormat;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.Map;
import java.util.Set;

/**
 * 该类用于展示与消息通道{@link IMessageChannel}相关的功能接口
 * 使用该服务可以实现本地与云端实例的消息通信。
 */
public class MessageChannelActivity extends BasePlayActivity {

    private FrameLayout mContainer;
    private SwitchCompat mSwShowOrHide;
    private LinearLayoutCompat mLlButtons;
    private Button mBtnAckMsg, mBtnUidAckMsg, mBtnTimeoutMsg, mBtnUidTimeoutMsg;
    private TextView mTvOnlineCid;
    private final MessageChannelController controller = new MessageChannelController();


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
        mTvOnlineCid = findViewById(R.id.tv_online_cid);

        mSwShowOrHide.setOnCheckedChangeListener((buttonView, isChecked) -> {
            mLlButtons.setVisibility(isChecked ? View.VISIBLE : View.GONE);
        });

        mBtnAckMsg.setOnClickListener(v -> {
            /*
             * 发送回执消息到云端应用(当云端只有一个应用注册消息通道时使用)
             *
             * @param payload 发送内容，size：60KB
             * @param needAck 是否需要云端Ack回执
             * @return 消息实体
             */
            IMessageChannel.IChannelMessage msg = controller.sendMessage("msg", true);
            Log.i(TAG, "msg: " + msg);
        });
        mBtnUidAckMsg.setOnClickListener(v -> {
            /*
             * 发送回执消息到云端应用(当云端有多个应用注册消息通道时使用，需要指定目标用户ID，即应用包名)
             *
             * @param payload        发送内容，size：60KB
             * @param needAck        是否需要云端Ack回执
             * @param destChannelUid 目标用户消息通道ID
             * @return 消息实体
             */
            IMessageChannel.IChannelMessage msg = controller.sendMessage(controller.getTopOnlineChannelUid(), "msg", true);
            Log.i(TAG, "msg: " + msg);
        });
        mBtnTimeoutMsg.setOnClickListener(v -> {
            /*
             * 发送超时消息到云端应用(当云端只有一个应用注册消息通道时使用)
             *
             * @param payload 发送内容，size：60KB
             * @param timeout 消息超时时长，单位：ms，需要大于0；当小于等于0时，通过
             *                  {@link com.volcengine.cloudphone.apiservice.IMessageChannel.IMessageReceiver#onError(int, String)}
             *                  返回错误信息
             * @return 消息实体
             */
            IMessageChannel.IChannelMessage msg = controller.sendMessage("msg", 3000);
            Log.i(TAG, "msg: " + msg);
        });
        mBtnUidTimeoutMsg.setOnClickListener(v -> {
            /*
             * 发送超时消息到云端应用(当云端有多个应用注册消息通道时使用，需要指定目标用户ID，即应用包名)
             *
             * @param payload        发送内容，size：60KB
             * @param timeout        消息超时时长，单位：ms，需要大于0；当小于等于0时，通过
             *                         {@link com.volcengine.cloudphone.apiservice.IMessageChannel.IMessageReceiver#onError(int, String)}
             *                         返回错误信息
             * @param destChannelUid 目标用户消息通道ID
             * @return 消息实体
             */
            IMessageChannel.IChannelMessage msg = controller.sendMessage(controller.getTopOnlineChannelUid(), "msg", 3000);
            Log.i(TAG, "msg: " + msg);
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
        // 初始化消息通道
        controller.initMessageChannel();
    }


    class MessageChannelController implements IMessageChannel.IMessageReceiver {
        private static final String TAG = "MessageChannel";
        private IMessageChannel messageChannel;
        private final Map<String, Boolean> channelConnectState = new HashMap<>(4);

        public void initMessageChannel() {
            channelConnectState.clear();
            messageChannel = VePhoneEngine.getInstance().getMessageChannel();
            if (messageChannel != null) {
                messageChannel.setMessageListener(this);
            }
        }

        public IMessageChannel.IChannelMessage sendMessage(String payload, long timeoutInMillis) {
            IMessageChannel mc = getOnlineChannel(null);
            return mc == null ? null : mc.sendMessage(payload, timeoutInMillis);
        }

        public IMessageChannel.IChannelMessage sendMessage(String payload, boolean needAck) {
            IMessageChannel mc = getOnlineChannel(null);
            return mc == null ? null : mc.sendMessage(payload, needAck);
        }

        public IMessageChannel.IChannelMessage sendMessage(String channelUid, String payload, boolean needAck) {
            IMessageChannel mc = getOnlineChannel(channelUid);
            return mc == null ? null : mc.sendMessage(payload, needAck, channelUid);
        }

        public IMessageChannel.IChannelMessage sendMessage(String channelUid, String payload, long timeoutInMillis) {
            IMessageChannel mc = getOnlineChannel(channelUid);
            return mc == null ? null : mc.sendMessage(payload, timeoutInMillis, channelUid);
        }

        private @Nullable IMessageChannel getOnlineChannel(@Nullable String targetChannelUid) {
            IMessageChannel mc = messageChannel;
            if (mc == null) {
                Log.d(TAG, "sendMessage: 当前messageChannel未初始化");
                return null;
            }
            if (TextUtils.isEmpty(targetChannelUid)) {
                if (!channelConnectState.containsValue(Boolean.TRUE)) {
                    Log.d(TAG, "sendMessage: 当前无远端连接，无法发送消息");
                    return null;
                }
            } else {
                if (channelConnectState.get(targetChannelUid) != Boolean.TRUE) {
                    Log.d(TAG, "sendMessage: 当前远端用户" + targetChannelUid + "未连接，无法发送消息");
                    return null;
                }
            }
            return mc;
        }

        public @NonNull Set<String> getAllChannelUids() {
            return channelConnectState.keySet();
        }

        public @NonNull Set<String> getOnlineChannelUids() {
            Set<String> set = new HashSet<>(4);
            for (Map.Entry<String, Boolean> entry : channelConnectState.entrySet()) {
                if (Boolean.TRUE.equals(entry.getValue())) {
                    set.add(entry.getKey());
                }
            }
            return set;
        }

        public @Nullable String getTopOnlineChannelUid() {
            Set<String> set = getOnlineChannelUids();
            Iterator<String> iterator = set.iterator();
            return iterator.hasNext() ? iterator.next() : null;
        }

        /**
         * 消息接收回调
         *
         * @param message 接收的消息实体
         */
        @Override
        public void onReceiveMessage(IMessageChannel.IChannelMessage message) {
            Log.d(TAG, "onReceiveMessage: message:" + message);
        }

        /**
         * 消息接收回调
         *
         * @param message 接收的消息实体
         */
        @Override
        public void onReceiveBinaryMessage(IMessageChannel.IChannelBinaryMessage message) {
            Log.d(TAG, "onReceiveBinaryMessage: message:" + message);
        }

        /**
         * 发送消息结果回调
         *
         * @param success 是否发送成功
         * @param messageId 消息ID
         */
        @Override
        public void onSentResult(boolean success, String messageId) {
            Log.d(TAG, "onSentResult: success:" + success + ", messageId:" + messageId);
        }

        @Override
        public void ready() {
            Log.d(TAG, "ready");
        }

        /**
         * 错误信息回调
         *
         * @param code 错误码
         * @param msg 错误信息
         */
        @Override
        public void onError(int code, String msg) {
            Log.d(TAG, "onError: code:" + code + ", msg:" + msg);
        }

        /**
         * 云端游戏在线回调，建议在发送消息前监听该回调检查通道是否已连接
         *
         * @param channelUid 云端游戏的用户ID
         */
        @Override
        public void onRemoteOnline(String channelUid) {
            Log.d(TAG, "onRemoteOnline: channelUid:" + channelUid);
            boolean isFirstConnect = channelConnectState.isEmpty();
            channelConnectState.put(channelUid, true);
            if (isFirstConnect) {
                onFirstConnectedInSession();
            }
            onOnlineStateChanged();
        }

        /**
         * 云端游戏离线回调
         *
         * @param channelUid 云端游戏的用户ID
         */
        @Override
        public void onRemoteOffline(String channelUid) {
            Log.d(TAG, "onRemoteOffline: channelUid:" + channelUid);
            channelConnectState.put(channelUid, false);
            onOnlineStateChanged();
        }

        private void onFirstConnectedInSession() {
            // 消息通道首次连接成功
        }

        private void onOnlineStateChanged() {
            mTvOnlineCid.setText(MessageFormat.format("在线用户：\n{0}", getOnlineChannelUids()));
        }
    }
}
