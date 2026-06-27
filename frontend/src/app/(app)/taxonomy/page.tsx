"use client";

import { PageHeader } from "@/components/page-header";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { RequirePermission } from "@/components/require-permission";
import { EmptyState } from "@/components/empty-state";
import { BlueprintsTab } from "@/features/taxonomy/blueprints-tab";
import { BooksTab } from "@/features/taxonomy/books-tab";
import { KnowledgePointsTab } from "@/features/taxonomy/knowledge-points-tab";
import { TagsTab } from "@/features/taxonomy/tags-tab";
import { useT } from "@/lib/i18n/provider";

export default function TaxonomyPage() {
  const t = useT();
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader
        eyebrow={t("taxonomy.eyebrow")}
        title={t("taxonomy.title")}
        description={t("taxonomy.description")}
      />
      <RequirePermission
        perm="admin:manage_taxonomy"
        fallback={
          <EmptyState
            title={t("taxonomy.notAvailable")}
            description={t("taxonomy.notAvailableDesc")}
          />
        }
      >
        <Tabs defaultValue="blueprints">
          <TabsList>
            <TabsTrigger value="blueprints">{t("taxonomy.tabBlueprints")}</TabsTrigger>
            <TabsTrigger value="books">{t("taxonomy.tabBooks")}</TabsTrigger>
            <TabsTrigger value="kps">{t("taxonomy.tabKps")}</TabsTrigger>
            <TabsTrigger value="tags">{t("taxonomy.tabTags")}</TabsTrigger>
          </TabsList>
          <TabsContent value="blueprints"><BlueprintsTab /></TabsContent>
          <TabsContent value="books"><BooksTab /></TabsContent>
          <TabsContent value="kps"><KnowledgePointsTab /></TabsContent>
          <TabsContent value="tags"><TagsTab /></TabsContent>
        </Tabs>
      </RequirePermission>
    </div>
  );
}
