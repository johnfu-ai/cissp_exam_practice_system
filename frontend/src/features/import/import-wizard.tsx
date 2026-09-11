"use client";

import { useRef, useState } from "react";
import {
  useDatasets,
  useCreateRun,
  useCommitRun,
  useRollbackRun,
  useUploadDataset,
  usePasteMarkdown,
} from "@/lib/api/etl";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Eyebrow } from "@/components/eyebrow";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Loading } from "@/components/loading";
import { ErrorState } from "@/components/error-state";
import { EmptyState } from "@/components/empty-state";
import { toast } from "@/components/ui/sonner";
import { useT } from "@/lib/i18n/provider";
import type { EtlRun } from "@/lib/api/types";
import {
  CANONICAL_IMPORT_FIELDS,
  REQUIRED_IMPORT_FIELDS,
  autoMapHeaders,
  buildImportTemplateCsv,
  downloadTextFile,
  parseCsvHeaders,
  remapCsv,
  type CanonicalImportField,
} from "@/lib/import-template";

const SKIP = "__skip__";

function Count({ label, value, tone }: { label: string; value: number; tone?: "create" | "update" | "muted" | "error" }) {
  const color =
    tone === "create" ? "text-success" :
    tone === "update" ? "text-primary" :
    tone === "error" ? "text-destructive" : "text-foreground";
  return (
    <div className="rounded-md border p-3 text-center">
      <div className={`text-2xl font-semibold tabular-nums ${color}`}>{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

export function ImportWizard() {
  const t = useT();
  const datasets = useDatasets();
  const createRun = useCreateRun();
  const commit = useCommitRun();
  const rollback = useRollbackRun();
  const upload = useUploadDataset();
  const paste = usePasteMarkdown();
  const [run, setRun] = useState<EtlRun | null>(null);
  const [activeSlug, setActiveSlug] = useState<string | null>(null);
  const [uploadSlug, setUploadSlug] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [pasteMarkdown, setPasteMarkdown] = useState("");
  const [pasteSlug, setPasteSlug] = useState("");
  const [csvHeaders, setCsvHeaders] = useState<string[]>([]);
  const [csvText, setCsvText] = useState<string | null>(null);
  const [mapping, setMapping] = useState<Record<string, CanonicalImportField | "">>({});
  const fileInputRef = useRef<HTMLInputElement>(null);

  function preview(slug: string) {
    setActiveSlug(slug);
    createRun.mutate(slug, {
      onSuccess: (r) => setRun(r),
      onError: () => toast.error(t("importWiz.toastPreviewFail")),
    });
  }

  async function onFileChange(file: File | null) {
    setUploadFile(file);
    setCsvHeaders([]);
    setCsvText(null);
    setMapping({});
    if (!file || !file.name.toLowerCase().endsWith(".csv")) return;
    const text = await file.text();
    const headers = parseCsvHeaders(text);
    setCsvText(text);
    setCsvHeaders(headers);
    setMapping(autoMapHeaders(headers));
  }

  async function doUpload() {
    const slug = uploadSlug.trim();
    if (!slug) {
      toast.error(t("importWiz.slugRequired"));
      return;
    }
    if (!uploadFile) {
      toast.error(t("importWiz.fileRequired"));
      return;
    }

    let file = uploadFile;
    if (csvText && csvHeaders.length > 0) {
      const mappedRequired = REQUIRED_IMPORT_FIELDS.every((f) =>
        Object.values(mapping).includes(f),
      );
      if (!mappedRequired) {
        toast.error(t("importWiz.mappingRequired"));
        return;
      }
      const remapped = remapCsv(csvText, mapping);
      file = new File([remapped], uploadFile.name, { type: "text/csv" });
    }

    upload.mutate(
      { file, datasetSlug: slug },
      {
        onSuccess: (r) => {
          setRun(r);
          setActiveSlug(r.dataset_slug);
          toast.success(t("importWiz.toastUploaded"));
        },
        onError: () => toast.error(t("importWiz.toastUploadFail")),
      },
    );
  }

  function doPaste() {
    const md = pasteMarkdown.trim();
    if (!md) {
      toast.error(t("importWiz.toastPasteFail"));
      return;
    }
    paste.mutate(
      { markdown: md, dataset_slug: pasteSlug.trim() || undefined },
      {
        onSuccess: (r) => {
          setRun(r);
          setActiveSlug(r.dataset_slug);
          toast.success(t("importWiz.toastUploaded"));
        },
        onError: () => toast.error(t("importWiz.toastPasteFail")),
      },
    );
  }

  function doCommit() {
    if (!run) return;
    commit.mutate(run.run_id, {
      onSuccess: (r) => {
        setRun((cur) => (cur ? { ...cur, phase: r.phase } : cur));
        toast.success(t("importWiz.toastCommitted"));
      },
      onError: () => toast.error(t("importWiz.toastCommitFail")),
    });
  }

  function doRollback() {
    if (!run) return;
    rollback.mutate(run.run_id, {
      onSuccess: (r) => {
        setRun((cur) => (cur ? { ...cur, phase: r.phase } : cur));
        toast.message(t("importWiz.toastDiscarded"));
      },
      onError: () => toast.error(t("importWiz.toastDiscardFail")),
    });
  }

  if (datasets.isLoading) return <Loading label={t("importWiz.loadingDatasets")} />;
  if (datasets.isError) {
    return <ErrorState message={t("importWiz.loadFailed")} onRetry={() => datasets.refetch()} />;
  }

  const summary = run?.preview_summary;

  return (
    <div className="space-y-8">
      <section>
        <Eyebrow className="mb-3">{t("importWiz.upload")}</Eyebrow>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("importWiz.upload")}</CardTitle>
            <p className="text-xs text-muted-foreground">{t("importWiz.uploadDesc")}</p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() =>
                  downloadTextFile("cissp-import-template.csv", buildImportTemplateCsv())
                }
              >
                {t("importWiz.downloadTemplate")}
              </Button>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label htmlFor="upload-slug" className="text-xs text-muted-foreground">
                  {t("importWiz.datasetName")}
                </label>
                <Input
                  id="upload-slug"
                  value={uploadSlug}
                  onChange={(e) => setUploadSlug(e.target.value)}
                  placeholder={t("importWiz.datasetNamePlaceholder")}
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="upload-file" className="text-xs text-muted-foreground">
                  {t("importWiz.acceptedFormats")}
                </label>
                <Input
                  id="upload-file"
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.xlsx,.json"
                  onChange={(e) => void onFileChange(e.target.files?.[0] ?? null)}
                />
              </div>
            </div>

            {csvHeaders.length > 0 && (
              <div className="space-y-3 rounded-md border p-3">
                <div>
                  <h4 className="text-sm font-medium">{t("importWiz.fieldMapping")}</h4>
                  <p className="text-xs text-muted-foreground">{t("importWiz.fieldMappingDesc")}</p>
                </div>
                <div className="grid gap-2">
                  {csvHeaders.map((h) => (
                    <div key={h} className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 text-sm">
                      <span className="truncate font-mono text-xs">{h}</span>
                      <span className="text-muted-foreground">→</span>
                      <Select
                        value={mapping[h] || SKIP}
                        onValueChange={(v) =>
                          setMapping((m) => ({
                            ...m,
                            [h]: v === SKIP ? "" : (v as CanonicalImportField),
                          }))
                        }
                      >
                        <SelectTrigger className="h-8">
                          <SelectValue placeholder={t("importWiz.skipColumn")} />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value={SKIP}>{t("importWiz.skipColumn")}</SelectItem>
                          {CANONICAL_IMPORT_FIELDS.map((f) => (
                            <SelectItem key={f} value={f}>
                              {f}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex items-center gap-3">
              <Button size="sm" onClick={() => void doUpload()} disabled={upload.isPending}>
                {upload.isPending ? t("importWiz.uploading") : t("importWiz.uploadAndPreview")}
              </Button>
              {uploadFile && (
                <span className="text-xs text-muted-foreground">{uploadFile.name}</span>
              )}
            </div>
          </CardContent>
        </Card>
      </section>

      <section>
        <Eyebrow className="mb-3">{t("importWiz.paste")}</Eyebrow>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("importWiz.paste")}</CardTitle>
            <p className="text-xs text-muted-foreground">{t("importWiz.pasteDesc")}</p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="paste-slug" className="text-xs text-muted-foreground">
                {t("importWiz.datasetName")}
              </label>
              <Input
                id="paste-slug"
                value={pasteSlug}
                onChange={(e) => setPasteSlug(e.target.value)}
                placeholder={t("importWiz.datasetNamePlaceholder")}
              />
            </div>
            <Textarea
              id="paste-markdown"
              value={pasteMarkdown}
              onChange={(e) => setPasteMarkdown(e.target.value)}
              placeholder={t("importWiz.pastePlaceholder")}
              rows={10}
              className="font-mono text-sm"
            />
            <Button size="sm" onClick={doPaste} disabled={paste.isPending}>
              {paste.isPending ? t("importWiz.pastePreviewing") : t("importWiz.pastePreview")}
            </Button>
          </CardContent>
        </Card>
      </section>

      <section>
        <Eyebrow className="mb-3">{t("importWiz.datasets")}</Eyebrow>
        {datasets.data && datasets.data.length === 0 ? (
          <EmptyState title={t("importWiz.noDatasets")} description={t("importWiz.noDatasetsDesc")} />
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {datasets.data?.map((d) => (
              <Card key={d.id} hover>
                <CardHeader>
                  <CardTitle className="text-base">{d.name}</CardTitle>
                  <p className="text-xs text-muted-foreground">{d.source_path}</p>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex flex-wrap gap-2 text-xs">
                    <Badge variant="secondary">{t("importWiz.nQuestions", { n: d.total_questions })}</Badge>
                    {d.languages.map((l) => (
                      <Badge key={l} variant="outline">{l}</Badge>
                    ))}
                  </div>
                  <Button
                    size="sm"
                    onClick={() => preview(d.slug)}
                    disabled={createRun.isPending && activeSlug === d.slug}
                  >
                    {createRun.isPending && activeSlug === d.slug ? t("importWiz.previewing") : t("importWiz.previewImport")}
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      {run && summary && (
        <section>
          <Eyebrow className="mb-3">{t("importWiz.preview")}</Eyebrow>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>{t("importWiz.previewOf", { slug: activeSlug ?? "" })}</CardTitle>
              <Badge variant={run.phase === "committed" ? "success" : run.phase === "rolled_back" ? "destructive" : "secondary"}>
                {run.phase}
              </Badge>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                <Count label={t("importWiz.wouldCreate")} value={summary.would_create} tone="create" />
                <Count label={t("importWiz.wouldUpdate")} value={summary.would_update} tone="update" />
                <Count label={t("importWiz.unchanged")} value={summary.unchanged} tone="muted" />
                <Count label={t("importWiz.duplicates")} value={summary.duplicates ?? 0} tone="muted" />
                <Count label={t("importWiz.errors")} value={summary.errors.length} tone="error" />
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <h4 className="mb-1 text-sm font-medium">{t("importWiz.byType")}</h4>
                  <ul className="space-y-1 text-sm text-muted-foreground">
                    {Object.entries(summary.by_type).map(([k, v]) => (
                      <li key={k} className="flex justify-between">
                        <span>{k.replace(/_/g, " ")}</span>
                        <span>{v}</span>
                      </li>
                    ))}
                    {Object.keys(summary.by_type).length === 0 && <li>—</li>}
                  </ul>
                </div>
                <div>
                  <h4 className="mb-1 text-sm font-medium">{t("importWiz.byLanguage")}</h4>
                  <ul className="space-y-1 text-sm text-muted-foreground">
                    {Object.entries(summary.by_language).map(([k, v]) => (
                      <li key={k} className="flex justify-between">
                        <span>{k}</span>
                        <span>{v}</span>
                      </li>
                    ))}
                    {Object.keys(summary.by_language).length === 0 && <li>—</li>}
                  </ul>
                </div>
              </div>

              {(summary.near_duplicates?.length ?? 0) > 0 && (
                <div>
                  <h4 className="mb-2 text-sm font-medium">
                    {t("importWiz.nearDuplicates", { n: summary.near_duplicates!.length })}
                  </h4>
                  <p className="mb-2 text-xs text-muted-foreground">
                    {t("importWiz.nearDuplicatesDesc")}
                  </p>
                  <div className="max-h-48 overflow-y-auto rounded-md border">
                    <table className="w-full text-sm">
                      <thead className="sticky top-0 bg-muted/60">
                        <tr className="text-left text-muted-foreground">
                          <th className="px-3 py-2 font-medium">{t("importWiz.colExternalId")}</th>
                          <th className="px-3 py-2 font-medium">{t("importWiz.colSimilarity")}</th>
                          <th className="px-3 py-2 font-medium">{t("importWiz.colSimilarTo")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.near_duplicates!.map((w, i) => (
                          <tr key={`${w.external_id}-${i}`} className="border-t">
                            <td className="px-3 py-2 font-mono text-xs">{w.external_id}</td>
                            <td className="px-3 py-2 text-muted-foreground">
                              {Math.round(w.similarity * 100)}%
                            </td>
                            <td className="px-3 py-2 text-muted-foreground">{w.stem_excerpt}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {(summary.conflicts?.length ?? 0) > 0 && (
                <div>
                  <h4 className="mb-2 text-sm font-medium">
                    {t("importWiz.conflicts", { n: summary.conflicts!.length })}
                  </h4>
                  <div className="max-h-48 overflow-y-auto rounded-md border">
                    <table className="w-full text-sm">
                      <thead className="sticky top-0 bg-muted/60">
                        <tr className="text-left text-muted-foreground">
                          <th className="px-3 py-2 font-medium">{t("importWiz.colExternalId")}</th>
                          <th className="px-3 py-2 font-medium">{t("importWiz.colReason")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.conflicts!.map((c, i) => (
                          <tr key={`${c.external_id}-${i}`} className="border-t">
                            <td className="px-3 py-2 font-mono text-xs">{c.external_id}</td>
                            <td className="px-3 py-2 text-muted-foreground">{c.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {summary.errors.length > 0 && (
                <div>
                  <h4 className="mb-2 text-sm font-medium text-destructive">
                    {t("importWiz.validationIssues", { n: summary.errors.length })}
                  </h4>
                  <div className="max-h-64 overflow-y-auto rounded-md border">
                    <table className="w-full text-sm">
                      <thead className="sticky top-0 bg-muted/60">
                        <tr className="text-left text-muted-foreground">
                          <th className="px-3 py-2 font-medium">{t("importWiz.colRowId")}</th>
                          <th className="px-3 py-2 font-medium">{t("importWiz.colLanguage")}</th>
                          <th className="px-3 py-2 font-medium">{t("importWiz.colReason")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {summary.errors.map((e, i) => (
                          <tr key={`${e.external_id}-${i}`} className="border-t">
                            <td className="px-3 py-2 font-mono text-xs">{e.external_id ?? "—"}</td>
                            <td className="px-3 py-2">{e.language ?? "—"}</td>
                            <td className="px-3 py-2 text-muted-foreground">{e.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {run.phase === "preview" ? (
                <div className="flex flex-wrap gap-2">
                  <Button size="pill" onClick={doCommit} disabled={commit.isPending}>
                    {commit.isPending ? t("importWiz.committing") : t("importWiz.commitImport", { n: summary.would_create + summary.would_update })}
                  </Button>
                  <Button variant="outline" size="pill" onClick={doRollback} disabled={rollback.isPending}>
                    {t("importWiz.discard")}
                  </Button>
                </div>
              ) : (
                <Alert>
                  <AlertTitle>{run.phase === "committed" ? t("importWiz.committedTitle") : t("importWiz.discardedTitle")}</AlertTitle>
                  <AlertDescription>
                    {run.phase === "committed"
                      ? t("importWiz.committedDesc")
                      : t("importWiz.discardedDesc")}
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>
        </section>
      )}
    </div>
  );
}
