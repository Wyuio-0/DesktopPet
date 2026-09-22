import SwiftUI

public struct NoteEditModal: View {
    var existingNote: Note?
    var onSaved: (Note) -> Void
    @Environment(\.dismiss) var dismiss

    @State private var title: String = ""
    @State private var content: String = ""
    @State private var pinned: Bool = false

    public init(existingNote: Note? = nil, onSaved: @escaping (Note) -> Void) {
        self.existingNote = existingNote
        self.onSaved = onSaved
    }

    public var body: some View {
        NavigationStack {
            VStack(spacing: 12) {
                TextField("便签标题 (选填，留空自动提取第一行)", text: $title)
                    .font(.system(size: 16, weight: .bold))
                    .padding(10)
                    .background(Color.amiyaCardBg)
                    .cornerRadius(10)

                Toggle("置顶到便签本顶部", isOn: $pinned)
                    .padding(.horizontal, 4)

                TextEditor(text: $content)
                    .font(.system(size: 15))
                    .padding(8)
                    .background(Color.amiyaCardBg)
                    .cornerRadius(12)
            }
            .padding()
            .navigationTitle(existingNote == nil ? "写便签" : "编辑便签")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("取消") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("保存") {
                        save()
                    }
                    .disabled(content.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
            .onAppear {
                if let n = existingNote {
                    title = n.title
                    content = n.content
                    pinned = n.pinned
                }
            }
        }
    }

    private func save() {
        let trimmedContent = content.trimmingCharacters(in: .whitespaces)
        if var n = existingNote {
            n.title = title.isEmpty ? n.autoDeriveTitle() : title
            n.content = trimmedContent
            n.pinned = pinned
            NotesManager.shared.updateNote(n)
            onSaved(n)
        } else {
            let n = NotesManager.shared.addNote(content: trimmedContent, title: title, pinned: pinned)
            onSaved(n)
        }
        dismiss()
    }
}
