import Foundation
import Combine

public class NotesManager: ObservableObject {
    public static let shared = NotesManager()

    @Published public var notes: [Note] = []

    private let fileURL: URL

    private init() {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        fileURL = docs.appendingPathComponent("notes.json")
        load()
    }

    public func load() {
        guard FileManager.default.fileExists(atPath: fileURL.path) else {
            initSampleNotes()
            return
        }
        do {
            let data = try Data(contentsOf: fileURL)
            let items = try JSONDecoder().decode([Note].self, from: data)
            notes = sortNotes(items)
        } catch {
            print("Failed to load notes.json: \(error)")
        }
    }

    private func initSampleNotes() {
        notes = [
            Note(
                title: "罗德岛事务速记",
                content: "博士，下周三前记得提交《人工智能导论》课程大作业开题报告；另外周五晚别忘了参加博士生学术研讨会！",
                pinned: true
            ),
            Note(
                title: "待买物资备忘",
                content: "买一支 2B 涂卡铅笔、橡皮擦，以及罗德岛定制保温水杯~",
                pinned: false
            )
        ]
        save()
    }

    public func save() {
        do {
            let data = try JSONEncoder().encode(notes)
            try data.write(to: fileURL)
        } catch {
            print("Failed to save notes.json: \(error)")
        }
    }

    public func addNote(content: String, title: String? = nil, pinned: Bool = false) -> Note {
        let derivedTitle = title?.isEmpty == false ? title! : Note(content: content).autoDeriveTitle()
        let newNote = Note(title: derivedTitle, content: content, pinned: pinned)
        notes.insert(newNote, at: 0)
        notes = sortNotes(notes)
        save()
        return newNote
    }

    public func updateNote(_ note: Note) {
        if let idx = notes.firstIndex(where: { $0.id == note.id }) {
            var updated = note
            updated.updatedAt = Note.currentTimestamp()
            notes[idx] = updated
            notes = sortNotes(notes)
            save()
        }
    }

    public func deleteNote(id: String) {
        notes.removeAll { $0.id == id }
        save()
    }

    public func togglePin(id: String) {
        if let idx = notes.firstIndex(where: { $0.id == id }) {
            notes[idx].pinned.toggle()
            notes[idx].updatedAt = Note.currentTimestamp()
            notes = sortNotes(notes)
            save()
        }
    }

    private func sortNotes(_ items: [Note]) -> [Note] {
        return items.sorted {
            if $0.pinned != $1.pinned {
                return $0.pinned && !$1.pinned
            }
            return $0.updatedAt > $1.updatedAt
        }
    }
}
