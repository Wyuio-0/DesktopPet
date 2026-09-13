package com.amiya.pet.model

import android.content.Context
import android.content.SharedPreferences
import com.amiya.pet.R
import com.amiya.pet.floating.FloatingPetManager.PetState

/**
 * 皮肤模型定义
 */
data class PetSkin(
    val id: String,
    val name: String,
    val shortName: String,
    val description: String,
    val defaultResId: Int,
    val blinkResId: Int? = null,
    val dragResId: Int? = null,
    val focusResId: Int? = null,
    val urgentResId: Int? = null,
    val sleepResId: Int? = null,
    val themeColor: String = "#38BDF8"
) {
    /**
     * 根据当前桌宠状态获取对应差分立绘，如无差分自动降级回退到默认立绘
     */
    fun getDrawableForState(state: PetState): Int {
        return when (state) {
            PetState.NORMAL -> defaultResId
            PetState.DRAGGING -> dragResId ?: defaultResId
            PetState.FOCUSING -> focusResId ?: defaultResId
            PetState.URGENT -> urgentResId ?: defaultResId
            PetState.SLEEPY -> sleepResId ?: defaultResId
        }
    }
}

/**
 * 干员模型定义（预留多干员扩展架构）
 */
data class Operator(
    val id: String,
    val displayName: String,
    val emojiPrefix: String,
    val profession: String,
    val defaultSkinId: String,
    val skins: List<PetSkin>
) {
    fun getSkin(skinId: String): PetSkin {
        return skins.firstOrNull { it.id.equals(skinId, ignoreCase = true) }
            ?: skins.firstOrNull { it.id == defaultSkinId }
            ?: skins.first()
    }
}

/**
 * 桌宠皮肤与干员仓库（持久化、查询与切换管理器）
 */
object PetSkinRepository {

    private const val PREFS_NAME = "amiya_pet_prefs"
    private const val KEY_CURRENT_OPERATOR_ID = "pref_current_operator_id"
    private const val KEY_CURRENT_SKIN_ID = "pref_current_skin_id"

    // 默认干员与皮肤
    const val DEFAULT_OPERATOR_ID = "amiya"
    const val DEFAULT_SKIN_ID = "amiya_caster"

    val OPERATORS: List<Operator> = listOf(
        Operator(
            id = "amiya",
            displayName = "阿米娅",
            emojiPrefix = "🐰",
            profession = "罗德岛领袖",
            defaultSkinId = "amiya_caster",
            skins = listOf(
                PetSkin(
                    id = "amiya_caster",
                    name = "术师 · 庆典",
                    shortName = "术师",
                    description = "经典庆典巫师帽与花簇装束",
                    defaultResId = R.drawable.avatar_amiya,
                    blinkResId = R.drawable.avatar_amiya_blink,
                    dragResId = R.drawable.avatar_amiya_drag,
                    focusResId = R.drawable.avatar_amiya_focus,
                    urgentResId = R.drawable.avatar_amiya_urgent,
                    sleepResId = R.drawable.avatar_amiya_sleep,
                    themeColor = "#38BDF8"
                ),
                PetSkin(
                    id = "amiya_guard",
                    name = "近卫 · 影霄",
                    shortName = "骑士",
                    description = "近卫升变形态，执掌黑剑影霄，英姿飒爽",
                    defaultResId = R.drawable.avatar_amiya_guard,
                    blinkResId = R.drawable.avatar_amiya_guard_blink,
                    dragResId = R.drawable.avatar_amiya_guard_drag,
                    focusResId = R.drawable.avatar_amiya_guard_focus,
                    urgentResId = R.drawable.avatar_amiya_guard_urgent,
                    sleepResId = R.drawable.avatar_amiya_guard_sleep,
                    themeColor = "#818CF8"
                ),
                PetSkin(
                    id = "amiya_fresh",
                    name = "报童 · 见习",
                    shortName = "报童",
                    description = "见习联络者报童装，墨绿报童帽与邮差挎包",
                    defaultResId = R.drawable.avatar_amiya_fresh,
                    blinkResId = R.drawable.avatar_amiya_fresh_blink,
                    dragResId = R.drawable.avatar_amiya_fresh_drag,
                    focusResId = R.drawable.avatar_amiya_fresh_focus,
                    urgentResId = R.drawable.avatar_amiya_fresh_urgent,
                    sleepResId = R.drawable.avatar_amiya_fresh_sleep,
                    themeColor = "#34D399"
                )
            )
        )
    )

    private fun getPrefs(context: Context): SharedPreferences {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    /**
     * 获取当前选中的干员
     */
    fun getCurrentOperator(context: Context): Operator {
        val opId = getPrefs(context).getString(KEY_CURRENT_OPERATOR_ID, DEFAULT_OPERATOR_ID) ?: DEFAULT_OPERATOR_ID
        return OPERATORS.firstOrNull { it.id.equals(opId, ignoreCase = true) } ?: OPERATORS.first()
    }

    /**
     * 获取当前选中的皮肤
     */
    fun getCurrentSkin(context: Context): PetSkin {
        val op = getCurrentOperator(context)
        val skinId = getPrefs(context).getString(KEY_CURRENT_SKIN_ID, op.defaultSkinId) ?: op.defaultSkinId
        return op.getSkin(skinId)
    }

    /**
     * 切换当前皮肤
     */
    fun switchSkin(context: Context, skinId: String): PetSkin {
        val op = OPERATORS.first()
        val targetSkin = op.skins.firstOrNull { skin ->
            skin.id.equals(skinId, ignoreCase = true) ||
            skin.name.contains(skinId, ignoreCase = true) ||
            skin.shortName.equals(skinId, ignoreCase = true) ||
            (skinId.contains("guard", ignoreCase = true) && skin.id == "amiya_guard") ||
            (skinId.contains("knight", ignoreCase = true) && skin.id == "amiya_guard") ||
            (skinId.contains("骑士", ignoreCase = true) && skin.id == "amiya_guard") ||
            (skinId.contains("近卫", ignoreCase = true) && skin.id == "amiya_guard") ||
            (skinId.contains("影霄", ignoreCase = true) && skin.id == "amiya_guard") ||
            (skinId.contains("fresh", ignoreCase = true) && skin.id == "amiya_fresh") ||
            (skinId.contains("报童", ignoreCase = true) && skin.id == "amiya_fresh") ||
            (skinId.contains("见习", ignoreCase = true) && skin.id == "amiya_fresh") ||
            (skinId.contains("caster", ignoreCase = true) && skin.id == "amiya_caster") ||
            (skinId.contains("术师", ignoreCase = true) && skin.id == "amiya_caster") ||
            (skinId.contains("庆典", ignoreCase = true) && skin.id == "amiya_caster")
        } ?: op.skins.first()

        getPrefs(context).edit()
            .putString(KEY_CURRENT_OPERATOR_ID, op.id)
            .putString(KEY_CURRENT_SKIN_ID, targetSkin.id)
            .apply()

        return targetSkin
    }

    /**
     * 切换干员，默认选用该干员的默认皮肤
     */
    fun switchOperator(context: Context, operatorId: String, skinId: String? = null): PetSkin {
        val op = OPERATORS.firstOrNull {
            it.id.equals(operatorId, ignoreCase = true) ||
            it.displayName.contains(operatorId, ignoreCase = true)
        } ?: OPERATORS.first()

        val skin = if (!skinId.isNullOrBlank()) op.getSkin(skinId) else op.getSkin(op.defaultSkinId)

        getPrefs(context).edit()
            .putString(KEY_CURRENT_OPERATOR_ID, op.id)
            .putString(KEY_CURRENT_SKIN_ID, skin.id)
            .apply()

        return skin
    }

    /**
     * 获取所有可用皮肤扁平列表，方便 UI 快速遍历展示
     */
    fun getAllSkins(): List<Pair<Operator, PetSkin>> {
        val list = mutableListOf<Pair<Operator, PetSkin>>()
        for (op in OPERATORS) {
            for (skin in op.skins) {
                list.add(op to skin)
            }
        }
        return list
    }
}
