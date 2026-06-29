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
import { useT } from "@/lib/i18n/provider";
import { Trash2 } from "lucide-react";
import type { Book } from "@/lib/api/types";

function err(e: unknown, fallback: string) {
  toast.error(e instanceof ApiError && (e.status === 422 || e.status === 409) ? e.message : fallback);
}

export function BooksTab() {
  const t = useT();
  const books = useBooks();
  const create = useCreateBook();
  const remove = useDeleteBook();
  const [title, setTitle] = useState("");

  if (books.isLoading) return <Loading label={t("taxonomyBooks.loading")} />;
  if (books.isError) return <ErrorState message={t("taxonomyBooks.loadFailed")} onRetry={() => books.refetch()} />;

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="flex items-end gap-2 p-4">
          <Input className="flex-1" placeholder={t("taxonomyBooks.newBookTitle")} value={title} onChange={(e) => setTitle(e.target.value)} />
          <Button
            size="pill"
            onClick={() => {
              if (!title.trim()) return;
              create.mutate({ title: title.trim() }, {
                onSuccess: () => { setTitle(""); toast.success(t("taxonomyBooks.toastAdded")); },
                onError: (e) => err(e, t("taxonomyBooks.couldNotAddBook")),
              });
            }}
            disabled={create.isPending}
          >
            {t("taxonomyBooks.addBook")}
          </Button>
        </CardContent>
      </Card>
      {books.data?.map((b) => (
        <BookCard
          key={b.id}
          book={b}
          onDelete={() => {
            if (!window.confirm(t("taxonomyBooks.deleteBookConfirm", { title: b.title }))) return;
            remove.mutate(b.id, { onSuccess: () => toast.success(t("taxonomyBooks.toastDeleted")), onError: (e) => err(e, t("taxonomyBooks.couldNotDelete")) });
          }}
        />
      ))}
      {books.data?.length === 0 && <p className="text-sm text-muted-foreground">{t("taxonomyBooks.noBooks")}</p>}
    </div>
  );
}

function BookCard({ book, onDelete }: { book: Book; onDelete: () => void }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState(book.title);
  const update = useUpdateBook();
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">{book.title}</CardTitle>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={() => setOpen((o) => !o)}>{open ? t("taxonomyBooks.hide") : t("taxonomyBooks.chapters")}</Button>
          <Button variant="ghost" size="sm" className="text-destructive" onClick={onDelete}><Trash2 className="h-4 w-4" /></Button>
        </div>
      </CardHeader>
      {open && (
        <CardContent className="space-y-4">
          <div className="flex items-end gap-2">
            <Input value={title} onChange={(e) => setTitle(e.target.value)} />
            <Button variant="outline" size="sm" disabled={title === book.title || update.isPending}
              onClick={() => update.mutate({ id: book.id, body: { title } }, { onSuccess: () => toast.success(t("taxonomyBooks.toastSaved")), onError: (e) => err(e, t("taxonomyBooks.couldNotSave")) })}>
              {t("taxonomyBooks.rename")}
            </Button>
          </div>
          <ChapterEditor bookId={book.id} />
        </CardContent>
      )}
    </Card>
  );
}

function ChapterEditor({ bookId }: { bookId: string }) {
  const t = useT();
  const chapters = useChapters(bookId);
  const create = useCreateChapter();
  const update = useUpdateChapter();
  const remove = useDeleteChapter();
  const [order, setOrder] = useState("");
  const [title, setTitle] = useState("");

  return (
    <div className="space-y-2">
      {chapters.isLoading && <p className="text-sm text-muted-foreground">{t("taxonomyBooks.loadingChapters")}</p>}
      {chapters.data?.map((c) => (
        <ChapterRow
          key={c.id}
          order={c.order_index}
          title={c.title}
          onSave={(body) => update.mutate({ bookId, chapterId: c.id, body }, { onError: (e) => err(e, t("taxonomyBooks.couldNotSaveChapter")) })}
          onDelete={() => {
            if (!window.confirm(t("taxonomyBooks.deleteChapterConfirm", { title: c.title }))) return;
            remove.mutate({ bookId, chapterId: c.id }, { onError: (e) => err(e, t("taxonomyBooks.couldNotDeleteChapter")) });
          }}
        />
      ))}
      <div className="flex items-end gap-2 rounded-md border border-dashed p-2">
        <Input className="w-16" placeholder={t("taxonomyBooks.orderPlaceholder")} value={order} onChange={(e) => setOrder(e.target.value)} />
        <Input className="flex-1" placeholder={t("taxonomyBooks.chapterTitlePlaceholder")} value={title} onChange={(e) => setTitle(e.target.value)} />
        <Button size="sm" disabled={create.isPending}
          onClick={() => {
            if (!title.trim()) return;
            create.mutate({ bookId, body: { order_index: Number(order) || 0, title: title.trim() } }, {
              onSuccess: () => { setOrder(""); setTitle(""); },
              onError: (e) => err(e, t("taxonomyBooks.couldNotAddChapter")),
            });
          }}>
          {t("taxonomyBooks.add")}
        </Button>
      </div>
    </div>
  );
}

function ChapterRow({ order, title, onSave, onDelete }: { order: number; title: string; onSave: (b: { order_index: number; title: string }) => void; onDelete: () => void }) {
  const t = useT();
  const [o, setO] = useState(String(order));
  const [tt, setT] = useState(title);
  const dirty = o !== String(order) || tt !== title;
  return (
    <div className="flex items-center gap-2">
      <Input className="w-16" value={o} onChange={(e) => setO(e.target.value)} />
      <Input className="flex-1" value={tt} onChange={(e) => setT(e.target.value)} />
      <Button size="sm" variant="outline" disabled={!dirty} onClick={() => onSave({ order_index: Number(o), title: tt })}>{t("taxonomyBooks.save")}</Button>
      <Button size="sm" variant="ghost" className="text-destructive" onClick={onDelete}><Trash2 className="h-4 w-4" /></Button>
    </div>
  );
}
