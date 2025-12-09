package com.example.sdkdemo.feature;

import android.os.Bundle;
import android.util.Log;
import android.view.InputDevice;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.FrameLayout;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.appcompat.widget.LinearLayoutCompat;
import androidx.appcompat.widget.SwitchCompat;

import com.example.sdkdemo.R;
import com.example.sdkdemo.base.BasePlayActivity;
import com.example.sdkdemo.util.ScreenUtil;
import com.example.sdkdemo.util.SdkUtil;
import com.volcengine.cloudphone.gamepad.GamePadService;
import com.volcengine.cloudplay.gamepad.api.OnGamePadStatusListener;
import com.volcengine.cloudplay.gamepad.api.OnPhysicalDeviceListener;
import com.volcengine.cloudplay.gamepad.api.VeGameConsole;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import java.util.Map;

/**
 * 该类用于展示与游戏手柄{@link GamePadService}相关的功能接口
 */
public class GamePadServiceActivity extends BasePlayActivity {

    private ViewGroup mContainer;
    GamePadService mGamePadService;
    private SwitchCompat mSwShowOrHide;
    private LinearLayoutCompat mLlButtons;
    private Button mBtnShowGamePad, mBtnHideGamePad;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        setContentView(R.layout.activity_gamepad);
        initView();
        initPlayConfigAndStartPlay();
    }

    private void initView() {
        mContainer = findViewById(R.id.container);
        mSwShowOrHide = findViewById(R.id.sw_show_or_hide);
        mLlButtons = findViewById(R.id.ll_buttons);
        mBtnShowGamePad = findViewById(R.id.btn_show_game_pad);
        mBtnHideGamePad = findViewById(R.id.btn_hide_game_pad);

        mSwShowOrHide.setOnCheckedChangeListener((buttonView, isChecked) -> {
            mLlButtons.setVisibility(isChecked ? View.VISIBLE : View.GONE);
        });

        /**
         * showVirtual() -- 显示虚拟手柄
         *
         * @apiNote 显示虚拟手柄后，云游戏主容器如需屏蔽Touch事件，请务必调用VeGameEngine.getInstance().setInterceptTouchEvent(true)
         *
         * @return  10 -- 成功
         *          11 -- 失败，手柄未初始化
         *          12 -- 失败，已经是显示状态
         */
        mBtnShowGamePad.setOnClickListener(v -> {
            VeGameConsole.getInstance().showVirtual();
            VePhoneEngine.getInstance().setInterceptTouchEvent(true);
        });

        /**
         * hideVirtual() -- 隐藏虚拟手柄
         *
         * @apiNote 隐藏虚拟手柄后，云游戏主容器如需重新获取Touch事件，请务必调用VeGameEngine.getInstance().setInterceptTouchEvent(false)
         *
         * @return  10 -- 成功
         *          11 -- 失败，手柄未初始化
         *          13 -- 失败，已经是隐藏状态
         */
        mBtnHideGamePad.setOnClickListener(v -> {
            VeGameConsole.getInstance().hideVirtual();
            VePhoneEngine.getInstance().setInterceptTouchEvent(false);
        });

    }

    private void initVeGameConsole() {
        /**
         * init(Context context) -- 初始化VeGameConsole SDK
         *
         * @param context 手柄初始化所需上下文
         */
        VeGameConsole.getInstance().init(mContainer.getContext());

        /**
         * 加载VeGameConsole SDK虚拟手柄支持
         *
         * @param context 虚拟手柄初始化所需上下文
         * @param attachFrame 添加虚拟手柄的View层级，需为FrameLayout以及子类
         *
         * @return 虚拟手柄初始化的结果
         *           0 -- 初始化成功
         *           1 -- 初始化失败，context为空
         *           2 -- 初始化失败，attachFrame为空
         */
        VeGameConsole.getInstance().loadVirtualConsole(mContainer.getContext(), (FrameLayout) mContainer);

        /**
         * setGamePadService(GamePadService service) -- 设置GamePadService
         * 该service作为客户端与云端手柄事件传递桥梁，
         * 如果没有设置GamePadService手柄事件将无法传递到云端
         */
        VeGameConsole.getInstance().setGamePadService(VePhoneEngine.getInstance().getGamePadService());

        /**
         * 设置物理设备监听器
         */
        VeGameConsole.getInstance().setPhysicalDeviceListener(new OnPhysicalDeviceListener() {
            /**
             * 物理设备接入的回调
             *
             * @param device 物理设备
             */
            @Override
            public void onDeviceAdded(InputDevice device) {
                // 注册一个物理手柄到云端
                VeGameConsole.getInstance().registerGameConsoleDevice(device.getName(), device.getId());
            }

            /**
             * 物理设备移除的回调
             *
             * @param device 物理设备
             */
            @Override
            public void onDeviceRemoved(InputDevice device) {
                // 解除一个云端已注册的物理手柄
                VeGameConsole.getInstance().unregisterGameConsoleDevice(device.getName(), device.getId());
            }
        });

        /**
         * 设置云端设备状态变化监听器，一般注册/解注册后会收到此消息
         */
        VeGameConsole.getInstance().setGamePadStatusListener(new OnGamePadStatusListener() {
            /**
             * 云端手柄状态发生变化
             *
             * @param deviceId 设备ID，与注册手柄时传入一致
             * @param enable 已启用/已禁用
             */
            @Override
            public void onGamePadStatusChanged(int deviceId, boolean enable) {
                Log.d(TAG, "[onGamePadStatusChanged] deviceId: " + deviceId + ", enable: " + enable);
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
        /**
         * release() -- 释放手柄资源，建议放到onDestroy回调中执行
         */
        VeGameConsole.getInstance().release();
    }

    @Override
    public void finish() {
        VePhoneEngine.getInstance().stop();
        super.finish();
    }

    @Override
    public void onServiceInit(@NonNull Map<String, Object> extras) {
        super.onServiceInit(extras);
        initVeGameConsole(); // 游戏手柄的初始化
    }

}
