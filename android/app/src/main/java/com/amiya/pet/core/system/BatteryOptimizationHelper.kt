package com.amiya.pet.core.system

import android.app.AlarmManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import android.widget.Toast

/**
 * 手机系统电池优化与后台保活辅助工具
 * 解决国产系统与现代 Android (Doze 模式) 智能省电对桌宠和课表提醒的休眠冻结。
 */
object BatteryOptimizationHelper {

    data class BrandGuide(
        val brandName: String,
        val steps: List<String>
    )

    /**
     * 检查当前应用是否已经处于「忽略电池优化」白名单中 (不受 Doze 深度休眠限制)
     */
    fun isIgnoringBatteryOptimizations(context: Context): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val powerManager = context.getSystemService(Context.POWER_SERVICE) as? PowerManager
            return powerManager?.isIgnoringBatteryOptimizations(context.packageName) ?: true
        }
        return true
    }

    /**
     * 请求系统弹出「忽略电池优化」对话框 (将阿米娅加入电池白名单)
     */
    fun requestIgnoreBatteryOptimizations(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            try {
                val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                    data = Uri.parse("package:${context.packageName}")
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                context.startActivity(intent)
            } catch (e: Exception) {
                // 部分 ROM 屏蔽了该 Action，平滑降级至电池优化列表或应用详情页
                try {
                    val fallbackIntent = Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS).apply {
                        flags = Intent.FLAG_ACTIVITY_NEW_TASK
                    }
                    context.startActivity(fallbackIntent)
                } catch (_: Exception) {
                    openApplicationDetails(context)
                }
            }
        }
    }

    /**
     * 检查是否支持/已授权精准闹钟 (Android 12+ / S)
     */
    fun canScheduleExactAlarms(context: Context): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as? AlarmManager
            return alarmManager?.canScheduleExactAlarms() ?: true
        }
        return true
    }

    /**
     * 请求前往系统授予精准闹钟调度权限 (Android 12+)
     */
    fun requestExactAlarmPermission(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            try {
                val intent = Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM).apply {
                    data = Uri.parse("package:${context.packageName}")
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                context.startActivity(intent)
            } catch (e: Exception) {
                openApplicationDetails(context)
            }
        }
    }

    /**
     * 打开应用系统详情页 (应用信息)
     */
    fun openApplicationDetails(context: Context) {
        try {
            val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                data = Uri.parse("package:${context.packageName}")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
        } catch (e: Exception) {
            Toast.makeText(context, "无法打开系统设置，请手动前往设置 > 应用管理", Toast.LENGTH_SHORT).show()
        }
    }

    /**
     * 针对各大主流手机品牌，尝试直接拉起自启动管理或电池后台配置页
     */
    fun openVendorPowerSettings(context: Context) {
        val brand = Build.MANUFACTURER.lowercase()
        val intentList = mutableListOf<Intent>()

        when {
            brand.contains("xiaomi") || brand.contains("redmi") -> {
                // 小米 MIUI / HyperOS 自启动与神隐模式
                intentList.add(
                    Intent().setComponent(
                        ComponentName(
                            "com.miui.powerkeeper",
                            "com.miui.powerkeeper.ui.HiddenAppsConfigActivity"
                        )
                    ).putExtra("package_name", context.packageName).putExtra("package_label", "阿米娅桌宠")
                )
                intentList.add(
                    Intent().setComponent(
                        ComponentName(
                            "com.miui.securitycenter",
                            "com.miui.permcenter.autostart.AutoStartManagementActivity"
                        )
                    )
                )
            }
            brand.contains("huawei") || brand.contains("honor") -> {
                // 华为 HarmonyOS / EMUI 启动管理
                intentList.add(
                    Intent().setComponent(
                        ComponentName(
                            "com.huawei.systemmanager",
                            "com.huawei.systemmanager.startupmgr.ui.StartupNormalAppListActivity"
                        )
                    )
                )
                intentList.add(
                    Intent().setComponent(
                        ComponentName(
                            "com.huawei.systemmanager",
                            "com.huawei.systemmanager.optimize.process.ProtectActivity"
                        )
                    )
                )
            }
            brand.contains("oppo") || brand.contains("oneplus") || brand.contains("realme") -> {
                // OPPO ColorOS / 一加 / 坚果 自启动
                intentList.add(
                    Intent().setComponent(
                        ComponentName(
                            "com.coloros.safecenter",
                            "com.coloros.safecenter.permission.startup.StartupAppListActivity"
                        )
                    )
                )
                intentList.add(
                    Intent().setComponent(
                        ComponentName(
                            "com.coloros.safecenter",
                            "com.coloros.safecenter.permission.floatwindow.FloatWindowListActivity"
                        )
                    )
                )
            }
            brand.contains("vivo") || brand.contains("iqoo") -> {
                // vivo OriginOS / iQOO 后台高耗电与自启动
                intentList.add(
                    Intent().setComponent(
                        ComponentName(
                            "com.iqoo.secure",
                            "com.iqoo.secure.ui.phoneoptimize.AddWhiteListActivity"
                        )
                    )
                )
                intentList.add(
                    Intent().setComponent(
                        ComponentName(
                            "com.vivo.permissionmanager",
                            "com.vivo.permissionmanager.activity.PurviewTabActivity"
                        )
                    )
                )
            }
            brand.contains("samsung") -> {
                // 三星 One UI 电池未受限
                intentList.add(
                    Intent().setComponent(
                        ComponentName(
                            "com.samsung.android.lool",
                            "com.samsung.android.sm.ui.battery.BatteryActivity"
                        )
                    )
                )
            }
        }

        // 尝试启动厂商专属配置页
        for (intent in intentList) {
            try {
                intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK
                context.startActivity(intent)
                return
            } catch (_: Exception) {
                // 尝试下一个
            }
        }

        // 降级启动系统应用详情页
        openApplicationDetails(context)
    }

    /**
     * 获取针对当前设备的品牌防杀后台定制指南
     */
    fun getBrandGuide(): BrandGuide {
        val brand = Build.MANUFACTURER.lowercase()
        return when {
            brand.contains("xiaomi") || brand.contains("redmi") -> BrandGuide(
                brandName = "小米 / 红米 (MIUI / HyperOS)",
                steps = listOf(
                    "1. 应用信息 > 省电策略：选择「无限制」",
                    "2. 应用信息 > 自启动：勾选「允许自启动」与「允许关联启动」",
                    "3. 多任务界面：长按阿米娅卡片并点击「加锁 🔒」图标",
                    "4. 应用信息 > 权限管理：开启「后台弹出界面」与「悬浮窗」"
                )
            )
            brand.contains("huawei") || brand.contains("honor") -> BrandGuide(
                brandName = "华为 / 荣耀 (HarmonyOS / EMUI)",
                steps = listOf(
                    "1. 设置 > 应用和服务 > 应用启动管理：找到阿米娅，关闭自动管理，勾选「允许自启动/关联启动/后台活动」",
                    "2. 设置 > 电池 > 更多电池设置：关闭智能省电模式",
                    "3. 多任务界面：下拉阿米娅任务卡片进行加锁保护",
                    "4. 应用权限：开启「悬浮窗」与「常驻通知」"
                )
            )
            brand.contains("oppo") || brand.contains("oneplus") || brand.contains("realme") -> BrandGuide(
                brandName = "OPPO / 一加 / 真我 (ColorOS)",
                steps = listOf(
                    "1. 设置 > 电池 > 高级设置：关闭睡眠待机优化",
                    "2. 应用管理 > 阿米娅 > 耗电管理：开启「允许完全后台行为」与「允许自启动」",
                    "3. 多任务界面：点击右上角三个点，选择「锁定 🔒」",
                    "4. 权限管理：开启「显示在其他应用上层」"
                )
            )
            brand.contains("vivo") || brand.contains("iqoo") -> BrandGuide(
                brandName = "vivo / iQOO (OriginOS)",
                steps = listOf(
                    "1. 设置 > 电池 > 后台耗电管理：找到阿米娅，设置为「允许高耗电」",
                    "2. 设置 > 应用与权限 > 权限管理 > 自启动：开启阿米娅自启权限",
                    "3. 多任务界面：下拉阿米娅任务卡片点击「锁定」",
                    "4. 开启通知与悬浮窗常驻显示"
                )
            )
            brand.contains("samsung") -> BrandGuide(
                brandName = "三星 (One UI)",
                steps = listOf(
                    "1. 设置 > 应用程序 > 阿米娅 > 电池：选择「不受限制」",
                    "2. 设置 > 电池和设备维护 > 电池 > 后台使用限制：将阿米娅加入「永不休眠的应用程序」",
                    "3. 多任务界面：点击应用图标，选择「保持开启 / 锁定」",
                    "4. 确保常驻前台服务与通知开启"
                )
            )
            else -> BrandGuide(
                brandName = "通用 Android 系统 / 模拟器",
                steps = listOf(
                    "1. 电池设置：允许阿米娅「忽略电池优化」（不受后台限制）",
                    "2. 权限设置：允许「闹钟和提醒」精准调度",
                    "3. 多任务后台：将阿米娅任务卡片加锁，防止一键清理",
                    "4. 允许显示悬浮窗与高优先级通知推送"
                )
            )
        }
    }
}
