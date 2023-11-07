package com.example.sdkdemo.feature;

import android.app.Activity;
import android.content.Context;
import android.os.Vibrator;
import android.view.View;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.ScrollView;

import com.example.sdkdemo.R;
import com.example.sdkdemo.util.DialogUtils;
import com.volcengine.cloudphone.gamepad.GamePadService;
import com.volcengine.cloudplay.gamepad.api.VeGameConsole;
import com.volcengine.phone.VePhoneEngine;

public class PadConsoleManagerView {

    Vibrator vibrator;
    FrameLayout mContainer;

    GamePadService mGamePadService;
    private final DialogUtils.DialogWrapper mDialogWrapper;

    public PadConsoleManagerView(Context context, GamePadService gamePadService, Button button) {
        this.mGamePadService = gamePadService;
        vibrator = (Vibrator) context.getSystemService(Context.VIBRATOR_SERVICE);
        mContainer = ((Activity)context).findViewById(R.id.container);
        mDialogWrapper = DialogUtils.wrapper(new PadConsoleManagerView.TestView(context));
        button.setVisibility(View.VISIBLE);
        button.setOnClickListener(v -> mDialogWrapper.show());
    }

    private class TestView extends ScrollView {

        public TestView(Context context) {
            super(context);
            inflate(context, R.layout.dialog_pc, this);
            Button gamePadInit = findViewById(R.id.game_console_init);
            Button gamePadShow = findViewById(R.id.game_console_show);
            Button gamePadHide = findViewById(R.id.game_console_hide);
            Button gamePadRelease = findViewById(R.id.game_console_release);

            /**
             * loadConsole(int consoleId, Context context, FrameLayout attachFrame) -- 初始化虚拟手柄
             *
             * @param consoleId 默认为0
             * @param context 虚拟手柄初始化所需上下文
             * @param attachFrame 添加虚拟手柄的View层级，需为FrameLayout以及子类
             *
             * @return 虚拟手柄初始化的结果
             *          0 -- 初始化成功
             *          1 -- 初始化失败，context为空
             *          2 -- 初始化失败，attachFrame为空
             *
             *
             * setGamePadService(GamePadService service) -- 设置GamePadService
             * 该service作为客户端与云端手柄事件传递桥梁，
             * 如果没有设置GamePadService手柄事件将无法传递到云端
             */
            gamePadInit.setOnClickListener(v -> {
                VeGameConsole.getInstance().loadConsole(0, context, mContainer);
                VeGameConsole.getInstance().setGamePadService(
                        VePhoneEngine.getInstance().getGamePadService()
                );
            });

            /**
             * show() -- 显示手柄
             *
             * @apiNote 显示手柄后，云游戏主容器如需屏蔽Touch事件，请务必调用VeGameEngine.getInstance().setInterceptTouchEvent(true)
             *
             * @return  10 -- 成功
             *          11 -- 失败，手柄未初始化
             *          12 -- 失败，已经是显示状态
             */
            gamePadShow.setOnClickListener(v -> {
                VeGameConsole.getInstance().show();
                VePhoneEngine.getInstance().setInterceptTouchEvent(true);
            });

            /**
             * hide() -- 隐藏手柄
             *
             * @apiNote 隐藏手柄后，云游戏主容器如需重新获取Touch事件，请务必调用VeGameEngine.getInstance().setInterceptTouchEvent(false)
             *
             * @return  10 -- 成功
             *          11 -- 失败，手柄未初始化
             *          13 -- 失败，已经是隐藏状态
             */
            gamePadHide.setOnClickListener(v -> {
                VeGameConsole.getInstance().hide();
                VePhoneEngine.getInstance().setInterceptTouchEvent(false);
            });

            /**
             * release() -- 释放手柄资源
             */
            gamePadRelease.setOnClickListener(v -> VeGameConsole.getInstance().release());
        }

    }
}
