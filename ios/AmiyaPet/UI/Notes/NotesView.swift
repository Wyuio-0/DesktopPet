import SwiftUI

public struct NotesView: View {
    @ObservedObject var manager = NotesManager.shared
    @State private var searchText: String = ""
    @State private var editingNote: Note?
    @State private var isCreatingNote: Bool = false

    public init() {}

    private var filteredNotes: [Note] {
        if searchText.trimmingCharacters(in: .whitespaces).isEmpty {
            return manager.notes
        }
        return manager.notes.filter {
            $0.title.localizedCaseInsensitiveContains(searchText) ||
            $0.content.localizedCaseInsensitiveContains(searchText)
        }
    }

    public var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // 搜索栏
                HStack {
                    Image(systemName: "magnifyingglass")
                        .foregroundColor(.secondary)
                    TextField("搜索备忘便签...", text: $searchText)
                    if !searchText.isEmpty {
                        Button(action: { searchText = "" }) {
                            Image(systemName: "xmark.circle.fill")
                                .foregroundColor(.secondary)
                        }
                    }
                }
                .padding(10)
                .background(Color.amiyaCardBg)
                .cornerRadius(12)
                .padding(.horizontal)
                .padding(.vertical, 8)

                // 便签列表
                if filteredNotes.isEmpty {
                    VStack(spacing: 12) {
                        Spacer()
                        Image(systemName: "note.text")
                            .font(.system(size: 48))
                            .foregroundColor(.secondary.opacity(0.4))
                        Text("暂无战术备忘")
                            .font(.system(size: 15))
                            .foregroundColor(.secondary)
                        Spacer()
                    }
                } else {
                    List {
                        ForEach(filteredNotes) { note in
                            noteRow(for: note)
                                .contentShape(Rectangle())
                                .onTapGesture { editingNote = note }
                                .swipeActions(edge: .leading) {
                                    Button {
                                        manager.togglePin(id: note.id)
                                    } label: {
                                        Label(note.pinned ? "取消置顶" : "置顶", systemImage: note.pinned ? "pin.slash" : "pin")
                                    }
                                    .tint(.orange)
                                }
                                .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                                    Button(role: .destructive) {
                                        manager.deleteNote(id: note.id)
                                    } label: {
                                        Label("删除", systemImage: "trash")
                                    }
                                }
                        }
                    }
                    .listStyle(InsetGroupedListStyle())
                }
            }
            .navigationTitle("战术备忘")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { isCreatingNote = true }) {
                        Image(systemName: "square.and.pencil")
                    }
                }
            }
            .sheet(item: $editingNote) { note in
                NoteEditModal(existingNote: note) { _ in }
            }
            .sheet(isPresented: $isCreatingNote) {
                NoteEditModal { _ in }
            }
        }
    }

    private func noteRow(for note: Note) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                if note.pinned {
                    Image(systemName: "pin.fill")
                        .font(.system(size: 11))
                        .foregroundColor(.orange)
                }
                Text(note.title)
                    .font(.system(size: 16, weight: .bold))
                Spacer()
                Text(note.updatedAt)
                    .font(.system(size: 11))
                    .foregroundColor(.secondary)
            }

            Text(note.content)
                .font(.system(size: 13))
                .foregroundColor(.secondary)
                .lineLimit(3)
        }
        .padding(.vertical, 4)
    }
}
