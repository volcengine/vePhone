package com.example.sdkdemo.feature;

import android.os.Bundle;
import android.util.Log;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.widget.LinearLayoutCompat;
import androidx.appcompat.widget.SwitchCompat;

import com.example.sdkdemo.R;
import com.example.sdkdemo.util.ScreenUtil;
import com.example.sdkdemo.base.BasePlayActivity;
import com.example.sdkdemo.util.SdkUtil;
import com.volcengine.androidcloud.common.model.SimpleTouchEvent;
import com.volcengine.cloudphone.apiservice.TouchEventService;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import java.text.MessageFormat;
import java.util.List;
import java.util.Map;

/**
 * 该类用于展示与触控事件{@link TouchEventService}相关的功能接口的使用方法
 * 使用该服务，可以向云端实例发送触控事件来操作实例，
 * 也可以拦截发送给云端的触控事件，进行一定包装后，再发送给实例。
 */
public class TouchEventServiceActivity extends BasePlayActivity {

    private ViewGroup mContainer;
    private TouchEventService mTouchEventService;
    private SwitchCompat mSwShowOrHide;
    private LinearLayoutCompat mLlButtons;
    private Button mBtnSendMotionEvent;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        setContentView(R.layout.activity_touch_event);
        initView();
        initPlayConfigAndStartPlay();
    }

    private void initView() {
        mContainer = findViewById(R.id.container);
        mSwShowOrHide = findViewById(R.id.sw_show_or_hide);
        mLlButtons = findViewById(R.id.ll_buttons);
        mBtnSendMotionEvent = findViewById(R.id.btn_send_motion_event);

        mSwShowOrHide.setOnCheckedChangeListener((buttonView, isChecked) -> {
            mLlButtons.setVisibility(isChecked ? View.VISIBLE : View.GONE);
        });

        /**
         * 向云端实例发送触摸事件
         * int sendMotionEvent(int action,
         *                         @FloatRange(from = 0.0, to = 1.0) float offsetX,
         *                         @FloatRange(from = 0.0, to = 1.0) float offsetY)
         *
         * @param action 比如:
         *                  {@link MotionEvent#ACTION_DOWN}
         *                  {@link MotionEvent#ACTION_UP}
         *                  {@link MotionEvent#ACTION_CANCEL}
         *                  {@link MotionEvent#ACTION_POINTER_DOWN}
         *                  {@link MotionEvent#ACTION_POINTER_UP}
         *                  {@link MotionEvent#ACTION_MOVE}
         * @param offsetX 距离云端实例屏幕左侧的偏移量，取值范围[0.0, 1.0]
         * @param offsetY 距离云端实例屏幕顶部的偏移量，取值范围[0.0, 1.0]
         *
         * @return  0 -- 方法调用成功
         *          1 -- 方法调用失败
         */
        mBtnSendMotionEvent.setOnClickListener(v -> {
            if (mTouchEventService != null) {
                mTouchEventService.sendMotionEvent(MotionEvent.ACTION_DOWN, 0.5f, 0.9f);
                mTouchEventService.sendMotionEvent(MotionEvent.ACTION_MOVE, 0.5f, 0.3f);
                mTouchEventService.sendMotionEvent(MotionEvent.ACTION_UP, 0.5f, 0.3f);
            }
            else {
                Log.e(TAG, "mTouchEventService == null");
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
        mTouchEventService = VePhoneEngine.getInstance().getTouchEventService();
        if (mTouchEventService != null) {
            /**
             * void setInterceptSendTouchEvent(boolean intercept)
             * 设置是否拦截SDK向云端实例发送触控事件
             *
             * @param intercept true -- 拦截
             *                  false -- 不拦截
             */
            mTouchEventService.setInterceptSendTouchEvent(true);
            mTouchEventService.setSimpleTouchEventListener(new TouchEventService.SimpleTouchEventListener() {
                /**
                 * 触控事件列表回调，用户可在该回调中处理触控事件
                 *
                 * @param list 回传的触控事件列表
                 */
                @Override
                public void onSimpleTouchEvent(List<SimpleTouchEvent> list) {
                    Log.i(TAG, "SimpleTouchEventList: " + list);
                }
            });
        }
        else {
            Log.e(TAG, "mTouchEventService == null");
        }
    }

}
