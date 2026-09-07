package com.amiya.pet.core.parser

import android.content.Context
import com.amiya.pet.core.model.Action
import com.amiya.pet.core.model.Character
import org.json.JSONObject
import java.io.InputStreamReader

object CharacterParser {

    /**
     * 列举 assets/characters 下所有有效角色目录。
     */
    fun listCharacters(context: Context): List<String> {
        return try {
            context.assets.list("characters")?.filter { dirName ->
                try {
                    context.assets.open("characters/$dirName/config.json").close()
                    true
                } catch (e: Exception) {
                    false
                }
            } ?: listOf("amiya", "yuyuananjielina", "shenglinchuxue")
        } catch (e: Exception) {
            listOf("amiya", "yuyuananjielina", "shenglinchuxue")
        }
    }

    /**
     * 解析指定角色的 config.json 并扫描动作视频资产。
     */
    fun loadCharacter(context: Context, charKey: String): Character? {
        val configPath = "characters/$charKey/config.json"
        val jsonStr = try {
            context.assets.open(configPath).use { input ->
                InputStreamReader(input, Charsets.UTF_8).readText()
            }
        } catch (e: Exception) {
            e.printStackTrace()
            return null
        }

        return try {
            val root = JSONObject(jsonStr)
            val name = root.optString("name", charKey)
            val displayName = root.optString("display_name", name)
            val scale = root.optDouble("scale", 0.765).toFloat()

            // 解析 actions
            val actionsMap = mutableMapOf<String, Action>()
            val actionsObj = root.optJSONObject("actions")
            if (actionsObj != null) {
                val keys = actionsObj.keys()
                while (keys.hasNext()) {
                    val actName = keys.next()
                    val actObj = actionsObj.getJSONObject(actName)
                    val folder = actObj.optString("folder", actName)
                    val interval = actObj.optInt("interval", 18)
                    val loop = actObj.optBoolean("loop", false)
                    val random = actObj.optBoolean("random", false)
                    val loopCount = actObj.optInt("loop_count", 0)
                    val next = if (actObj.has("next")) actObj.optString("next") else null

                    // 检索该动作下的所有 webm 素材文件
                    val assetDir = "characters/$charKey/$folder"
                    val files = try {
                        context.assets.list(assetDir)?.filter { it.endsWith(".webm") }
                            ?.sorted()
                            ?.map { "$assetDir/$it" } ?: emptyList()
                    } catch (e: Exception) {
                        emptyList()
                    }

                    actionsMap[actName] = Action(
                        name = actName,
                        folder = folder,
                        interval = interval,
                        loop = loop,
                        random = random,
                        loopCount = loopCount,
                        next = next,
                        clips = files
                    )
                }
            }

            // 解析交互事件
            val interactionsMap = mutableMapOf<String, String>()
            val interObj = root.optJSONObject("interactions")
            if (interObj != null) {
                val keys = interObj.keys()
                while (keys.hasNext()) {
                    val k = keys.next()
                    interactionsMap[k] = interObj.getString(k)
                }
            }

            // 解析打招呼与睡眠休息时间
            val restObj = root.optJSONObject("rest")
            val idleToSit = parseRange(restObj?.optJSONArray("idle_to_sit"), 300 to 600)
            val sitToSleep = parseRange(restObj?.optJSONArray("sit_to_sleep"), 3600 to 7200)

            val greetingsList = mutableListOf<String>()
            val greetingsObj = root.optJSONObject("greetings")
            if (greetingsObj != null) {
                val morning = greetingsObj.optJSONObject("morning")?.optJSONArray("lines")
                if (morning != null) {
                    for (i in 0 until morning.length()) {
                        greetingsList.add(morning.getString(i))
                    }
                }
            }

            Character(
                key = charKey,
                name = name,
                displayName = displayName,
                scale = scale,
                actions = actionsMap,
                interactions = interactionsMap,
                idleToSitSec = idleToSit,
                sitToSleepSec = sitToSleep,
                greetingLines = greetingsList
            )
        } catch (e: Exception) {
            e.printStackTrace()
            null
        }
    }

    private fun parseRange(arr: org.json.JSONArray?, default: Pair<Int, Int>): Pair<Int, Int> {
        if (arr != null && arr.length() >= 2) {
            return arr.optInt(0, default.first) to arr.optInt(1, default.second)
        }
        return default
    }
}
