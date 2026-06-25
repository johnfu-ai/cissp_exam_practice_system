"use client";

import { useState } from "react";
import { useBooks, useChapters } from "@/lib/api/taxonomy";
import {
  useCreateBook, useUpdateBook, useDeleteBook,
  useCreateChapter, useUpdateChapter, useDeleteChapter,
} from "@/lib/api/taxonomy-admin";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { toast } from "@/components/ui/sonner";
import { ApiError } from "@/lib/api";
import { Trash2 } from "lucide-react";
import type { Book } from "@/lib/api/types";

function err(e: unknown, fallback: string) {
  toast.error(e instanceof ApiError && (e.status === 422 || e.status === 409) ? e.message : fallback);
}

export function BooksTab() {
  const books = useBooks();
  const create = useCreateBook();
  const remove = useDeleteBook();
  const [title, setTitle] = useState("");

  if (books.isLoading) return <Loading label="Loading books…" />;
  if (books.isError) return <ErrorState message="Could not load books." onRetry={() => books.refetch()} />;

  return (
    <div className="space-y-4">
      <div className="flex items-end gap-2 rounded-md border border-dashed p-3">
        <Input className="flex-1" placeholder="New book title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <Button
          onClick={() => {
            if (!title.trim()) return;
            create.mutate({ title: title.trim() }, {
              onSuccess: () => { setTitle(""); toast.success("Book added."); },
              onError: (e) => err(e, "Could not add book."),
            });
          }}
          disabled={create.isPending}
        >
          Add book
        </Button>
      </div>
      {books.data?.map((b) => (
        <BookCard
          key={b.id}
          book={b}
          onDelete={() => {
            if (!window.confirm(`Delete book "${b.title}"?`)) return;
            remove.mutate(b.id, { onSuccess: () => toast.success("Deleted."), onError: (e) => err(e, "Could not delete (may be referenced).") });
          }}
        />
      ))}
      {books.data?.length === 0 && <p className="text-sm text-muted-foreground">No books yet.</p>}
    </div>
  );
}

function BookCard({ book, onDelete }: { book: Book; onDelete: () => void }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState(book.title);
  const update = useUpdateBook();
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">{book.title}</CardTitle>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={() => setOpen((o) => !o)}>{open ? "Hide" : "Chapters"}</Button>
          <Button variant="ghost" size="sm" className="text-destructive" onClick={onDelete}><Trash2 className="h-4 w-4" /></Button>
        </div>
      </CardHeader>
      {open && (
        <CardContent className="space-y-4">
          <div className="flex items-end gap-2">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} />
            <Button variant="outline" size="sm" disabled={title === book.title || update.isPending}
              onClick={() => update.mutate({ id: book.id, body: { title } }, { onSuccess: () => toast.success("Saved."), onError: (e) => err(e, "Could not save.") })}>
              Rename
            </Button>
          </div>
          <ChapterEditor bookId={book.id} />
        </CardContent>
      )}
    </Card>
  );
}

function ChapterEditor({ bookId }: { bookId: string }) {
  const chapters = useChapters(bookId);
  const create = useCreateChapter();
  const update = useUpdateChapter();
  const remove = useDeleteChapter();
  const [order, setOrder] = useState("");
  const [title, setTitle] = useState("");

  return (
    <div className="space-y-2">
      {chapters.isLoading && <p className="text-sm text-muted-foreground">Loading chapters…</p>}
      {chapters.data?.map((c) => (
        <ChapterRow
          key={c.id}
          order={c.order_index}
          title={c.title}
          onSave={(body) => update.mutate({ bookId, chapterId: c.id, body }, { onError: (e) => err(e, "Could not save chapter.") })}
          onDelete={() => {
            if (!window.confirm(`Delete chapter "${c.title}"?`)) return;
            remove.mutate({ bookId, chapterId: c.id }, { onError: (e) => err(e, "Could not delete chapter.") });
          }}
        />
      ))}
      <div className="flex items-end gap-2 rounded-md border border-dashed p-2">
        <Input className="w-16" placeholder="#" value={order} onChange={(e) => setOrder(e.target.value)} />
        <Input className="flex-1" placeholder="Chapter title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <Button size="sm" disabled={create.isPending}
          onClick={() => {
            if (!title.trim()) return;
            create.mutate({ bookId, body: { order_index: Number(order) || 0, title: title.trim() } }, {
              onSuccess: () => { setOrder(""); setTitle(""); },
              onError: (e) => err(e, "Could not add chapter."),
            });
          }}>
          Add
        </Button>
      </div>
    </div>
  );
}

function ChapterRow({ order, title, onSave, onDelete }: { order: number; title: string; onSave: (b: { order_index: number; title: string }) => void; onDelete: () => void }) {
  const [o, setO] = useState(String(order));
  const [t, setT] = useState(title);
  const dirty = o !== String(order) || t !== title;
  return (
    <div className="flex items-center gap-2">
      <Input className="w-16" value={o} onChange={(e) => setO(e.target.value)} />
      <Input className="flex-1" value={t} onChange={(e) => setT(e.target.value)} />
      <Button size="sm" variant="outline" disabled={!dirty} onClick={() => onSave({ order_index: Number(o), title: t })}>Save</Button>
      <Button size="sm" variant="ghost" className="text-destructive" onClick={onDelete}><Trash2 className="h-4 w-4" /></Button>
    </div>
  );
}
