package com.example.sdkdemo.feature;

import android.os.Bundle;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;

import androidx.annotation.Nullable;
import androidx.appcompat.widget.LinearLayoutCompat;
import androidx.appcompat.widget.SwitchCompat;

import com.example.sdkdemo.R;
import com.example.sdkdemo.util.ScreenUtil;
import com.example.sdkdemo.base.BasePlayActivity;
import com.example.sdkdemo.util.SdkUtil;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

/**
 * 该类用于展示主功能以外的其他功能接口
 * 其中包括从云端拉取视频流的暂停与恢复、向云端实例发送按键事件、
 * 云端实例加载/关闭应用等。
 */
public class OthersActivity extends BasePlayActivity {

    private ViewGroup mContainer;
    private SwitchCompat mSwShowOrHide;
    private LinearLayoutCompat mLlButtons;
    private Button mBtnPause, mBtnResume, mBtnSendKeyEvent,
            mBtnLaunchApp, mBtnCloseApp;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        setContentView(R.layout.activity_others);
        initView();
        initPlayConfigAndStartPlay();
    }

    private void initView() {
        mContainer = findViewById(R.id.container);
        mSwShowOrHide = findViewById(R.id.sw_show_or_hide);
        mLlButtons = findViewById(R.id.ll_buttons);
        mBtnPause = findViewById(R.id.btn_pause);
        mBtnResume = findViewById(R.id.btn_resume);
        mBtnSendKeyEvent = findViewById(R.id.btn_send_key_event);
        mBtnLaunchApp = findViewById(R.id.btn_launch_app);
        mBtnCloseApp = findViewById(R.id.btn_close_app);

        mSwShowOrHide.setOnCheckedChangeListener((buttonView, isChecked) -> {
            mLlButtons.setVisibility(isChecked ? View.VISIBLE : View.GONE);
        });

        mBtnPause.setOnClickListener(view -> {
            /**
             * pause() -- 暂停从云端拉流
             */
            VePhoneEngine.getInstance().pause();
        });
        mBtnResume.setOnClickListener(view -> {
            /**
             * resume() -- 恢复从云端拉流
             */
            VePhoneEngine.getInstance().resume();
        });

        /**
         * 向云端实例发送键盘事件
         * int sendKeyEvent(int keyCode)
         * int sendKeyEvent(int action, int keyCode)
         *
         * @param action  事件类型，eg. {@link KeyEvent#ACTION_DOWN} etc.
         * @param keyCode 当前仅支持以下键盘事件：
         *                <li>{@link KeyEvent#KEYCODE_HOME}</li>
         *                <li>{@link KeyEvent#KEYCODE_BACK}</li>
         *                <li>{@link KeyEvent#KEYCODE_MENU}</li>
         *                <li>{@link KeyEvent#KEYCODE_APP_SWITCH}</li>
         *
         * @return 0 -- 调用成功
         *        -1 -- 调用失败或者不支持该keyCode
         */
        mBtnSendKeyEvent.setOnClickListener(v -> {
            VePhoneEngine.getInstance().sendKeyEvent(KeyEvent.KEYCODE_HOME);

//            VePhoneEngine.getInstance().sendKeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_BACK);
//            VePhoneEngine.getInstance().sendKeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_BACK);
        });

        /**
         * 云端实例加载应用
         * void launchApp(String packageName)
         *
         * 云端实例关闭应用
         * void closeApp(String packageName)
         *
         * @param packageName 云端应用包名
         *
         */
        mBtnLaunchApp.setOnClickListener(v -> {
            VePhoneEngine.getInstance().launchApp("com.android.settings"); // [设置]应用包名
        });
        mBtnCloseApp.setOnClickListener(v -> {
            VePhoneEngine.getInstance().closeApp("com.android.settings");
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


}
