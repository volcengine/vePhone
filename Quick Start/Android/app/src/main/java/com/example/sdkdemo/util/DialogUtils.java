package com.example.sdkdemo.util;

import android.app.Activity;
import android.app.AlertDialog;
import android.util.Log;
import android.view.View;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import java.lang.reflect.Field;
import java.util.Iterator;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;

public class DialogUtils {

    @NonNull
    public static DialogWrapper wrapper(){
        return new DialogWrapper(null);
    }

    @NonNull
    public static DialogWrapper wrapper(View content){
        return new DialogWrapper(content);
    }

    @Nullable
    public static AlertDialog.Builder builder() {
        List<Activity> list = getActivitiesByReflect();
        return !list.isEmpty() ? new AlertDialog.Builder(list.get(0)) : null;
    }

    @NonNull
    private static List<Activity> getActivitiesByReflect() {
        LinkedList<Activity> list = new LinkedList<>();
        Activity topActivity = null;

        try {
            Object activityThread = getActivityThread();
            Field mActivitiesField = activityThread.getClass().getDeclaredField("mActivities");
            mActivitiesField.setAccessible(true);
            Object mActivities = mActivitiesField.get(activityThread);
            if (!(mActivities instanceof Map)) {
                return list;
            }

            Map<Object, Object> binder_activityClientRecord_map = (Map) mActivities;
            Iterator var7 = binder_activityClientRecord_map.values().iterator();

            while (var7.hasNext()) {
                Object activityRecord = var7.next();
                Class activityClientRecordClass = activityRecord.getClass();
                Field activityField = activityClientRecordClass.getDeclaredField("activity");
                activityField.setAccessible(true);
                Activity activity = (Activity) activityField.get(activityRecord);
                if (topActivity == null) {
                    Field pausedField = activityClientRecordClass.getDeclaredField("paused");
                    pausedField.setAccessible(true);
                    if (!pausedField.getBoolean(activityRecord)) {
                        topActivity = activity;
                    } else {
                        list.add(activity);
                    }
                } else {
                    list.add(activity);
                }
            }
        } catch (Exception var13) {
            Log.e("UtilsActivityLifecycle", "getActivitiesByReflect: " + var13.getMessage());
        }

        if (topActivity != null) {
            list.addFirst(topActivity);
        }

        return list;
    }

    private static Object getActivityThread() {
        Object activityThread = getActivityThreadInActivityThreadStaticField();
        return activityThread != null ? activityThread : getActivityThreadInActivityThreadStaticMethod();
    }

    @Nullable
    private static Object getActivityThreadInActivityThreadStaticField() {
        try {
            Class activityThreadClass = Class.forName("android.app.ActivityThread");
            Field sCurrentActivityThreadField = activityThreadClass.getDeclaredField("sCurrentActivityThread");
            sCurrentActivityThreadField.setAccessible(true);
            return sCurrentActivityThreadField.get((Object) null);
        } catch (Exception var3) {
            Log.e("UtilsActivityLifecycle", "getActivityThreadInActivityThreadStaticField: " + var3.getMessage());
            return null;
        }
    }

    @Nullable
    private static Object getActivityThreadInActivityThreadStaticMethod() {
        try {
            Class activityThreadClass = Class.forName("android.app.ActivityThread");
            return activityThreadClass.getMethod("currentActivityThread").invoke((Object) null);
        } catch (Exception var2) {
            Log.e("UtilsActivityLifecycle", "getActivityThreadInActivityThreadStaticMethod: " + var2.getMessage());
            return null;
        }
    }

    public static class DialogWrapper {
        private AlertDialog mDialog;
        private final View mContentView;

        public DialogWrapper(@Nullable View contentView) {
            mContentView = contentView;
        }

        public void show() {
            if (mDialog == null) {
                if (mContentView != null) {
                    AlertDialog.Builder builder = DialogUtils.builder();
                    if (builder != null) {
                        mDialog = builder
                                .setView(mContentView)
                                .setNegativeButton("close", (dialog, which) -> dialog.dismiss())
                                .show();
                    }
                } else {
                    Log.w("TAG", "show: mContentView must not be null!");
                }
            }else {
                mDialog.show();
            }
        }

        public void show(String message) {
            if (mDialog == null) {
                AlertDialog.Builder builder = DialogUtils.builder();
                if (builder != null) {
                    mDialog = builder
                            .setMessage(message)
                            .setNegativeButton("close", (dialog, which) -> dialog.dismiss())
                            .show();
                }
            } else {
                mDialog.setMessage(message);
                if (!mDialog.isShowing()) {
                    mDialog.show();
                }
            }
        }

        public void release() {
            if (mDialog != null) {
                mDialog.dismiss();
                mDialog = null;
            }
        }
    }
}
