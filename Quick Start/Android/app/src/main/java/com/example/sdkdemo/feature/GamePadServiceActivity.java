package com.example.sdkdemo.feature;

import android.os.Bundle;
import android.util.Log;
import android.view.InputDevice;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.example.sdkdemo.R;
import com.example.sdkdemo.base.BasePlayActivity;
import com.example.sdkdemo.databinding.ActivityGamepadBinding;
import com.example.sdkdemo.util.ScreenUtil;
import com.example.sdkdemo.util.SdkUtil;
import com.volcengine.cloudphone.gamepad.GamePadService;
import com.volcengine.cloudplay.gamepad.api.ErrorCode;
import com.volcengine.cloudplay.gamepad.api.OnGamePadStatusListener;
import com.volcengine.cloudplay.gamepad.api.OnPhysicalDeviceListener;
import com.volcengine.cloudplay.gamepad.api.VeGameConsole;
import com.volcengine.phone.PhonePlayConfig;
import com.volcengine.phone.VePhoneEngine;

import java.text.MessageFormat;
import java.util.Map;

/**
 * 该类用于展示与游戏手柄{@link GamePadService}相关的功能接口
 */
public class GamePadServiceActivity extends BasePlayActivity {

    private ActivityGamepadBinding binding;

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScreenUtil.adaptHolePhone(this);
        binding = ActivityGamepadBinding.inflate(getLayoutInflater());
        setContentView(binding.getRoot());
        initView();
        initPlayConfigAndStartPlay();
    }

    private void initView() {
        binding.swShowOrHide.setOnCheckedChangeListener((buttonView, isChecked) -> {
            binding.llButtons.setVisibility(isChecked ? View.VISIBLE : View.GONE);
        });

        /*
         * showVirtual() -- 显示虚拟手柄
         *
         * @apiNote 显示虚拟手柄后，云游戏主容器如需屏蔽Touch事件，请务必调用VeGameEngine.getInstance().setInterceptTouchEvent(true)
         *
         * @return  10 -- 成功
         *          11 -- 失败，手柄未初始化
         *          12 -- 失败，已经是显示状态
         */
        binding.btnShowGamePad.setOnClickListener(v -> {
            VeGameConsole.getInstance().showVirtual();
            VePhoneEngine.getInstance().setInterceptTouchEvent(true);
        });

        /*
         * hideVirtual() -- 隐藏虚拟手柄
         *
         * @apiNote 隐藏虚拟手柄后，云游戏主容器如需重新获取Touch事件，请务必调用VeGameEngine.getInstance().setInterceptTouchEvent(false)
         *
         * @return  10 -- 成功
         *          11 -- 失败，手柄未初始化
         *          13 -- 失败，已经是隐藏状态
         */
        binding.btnHideGamePad.setOnClickListener(v -> {
            VeGameConsole.getInstance().hideVirtual();
            VePhoneEngine.getInstance().setInterceptTouchEvent(false);
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
                            .container(binding.container)
                            .podId(auth.podId)
                            .productId(auth.productId)
                            .enableLocalKeyboard(true)
                            .roundId(SdkUtil.getRoundId())
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
        /*
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
    public boolean dispatchKeyEvent(KeyEvent event) {
        return VeGameConsole.getInstance().dispatchKeyEvent(event)
                || super.dispatchKeyEvent(event);
    }

    @Override
    public boolean dispatchGenericMotionEvent(MotionEvent event) {
        return VeGameConsole.getInstance().dispatchGenericMotionEvent(event)
                || super.dispatchGenericMotionEvent(event);
    }

    @Override
    public void onServiceInit(@NonNull Map<String, Object> extras) {
        super.onServiceInit(extras);
        initVeGameConsole(); // 游戏手柄的初始化
    }

    private void initVeGameConsole() {
        /*
         * init(Context context) -- 初始化VeGameConsole SDK
         *
         * @param context 手柄初始化所需上下文
         */
        VeGameConsole.getInstance().init(getApplicationContext());

        /*
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
        VeGameConsole.getInstance().loadVirtualConsole(getApplicationContext(), binding.container);

        /*
         * setGamePadService(GamePadService service) -- 设置GamePadService
         * 该service作为客户端与云端手柄事件传递桥梁，
         * 如果没有设置GamePadService手柄事件将无法传递到云端
         */
        VeGameConsole.getInstance().setGamePadService(VePhoneEngine.getInstance().getGamePadService());

        /*
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
                int ret = VeGameConsole.getInstance().registerGameConsoleDevice(device.getName(), device.getId());
                String msg = "";
                switch (ret) {
                    case ErrorCode.ERROR_INIT_FAILED:
                        msg = "未初始化VeGameConsole";
                        break;
                    case ErrorCode.ERROR_REGISTER_OVER_LIMIT:
                        msg = "注册量超出限制";
                        break;
                    case ErrorCode.ERROR_REGISTER_INVALID_DEVICE:
                        msg = "注册设备ID无效";
                        break;
                    case ErrorCode.ERROR_DEVICE_ALREADY_REGISTERED:
                        msg = "设备重复注册";
                        break;
                    case ErrorCode.REGISTER_SUCCESS:
                        msg = "设备注册成功";
                        break;
                    default:
                        msg = "设备注册失败：" + ret;
                        break;
                }
                showToast("onDeviceAdded: id:" + device.getId() + ", " + msg);
            }

            /**
             * 物理设备移除的回调
             *
             * @param device 物理设备
             */
            @Override
            public void onDeviceRemoved(InputDevice device) {
                showToast("onDeviceRemoved: id:" + device.getId());
                // 解除一个云端已注册的物理手柄
                VeGameConsole.getInstance().unregisterGameConsoleDevice(device.getName(), device.getId());
            }
        });

        /*
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

}
