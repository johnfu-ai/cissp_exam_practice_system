"use client";

import { PageHeader } from "@/components/page-header";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { RequirePermission } from "@/components/require-permission";
import { EmptyState } from "@/components/empty-state";
import { BlueprintsTab } from "@/features/taxonomy/blueprints-tab";
import { BooksTab } from "@/features/taxonomy/books-tab";
import { KnowledgePointsTab } from "@/features/taxonomy/knowledge-points-tab";
import { TagsTab } from "@/features/taxonomy/tags-tab";

export default function TaxonomyPage() {
  return (
    <div>
      <PageHeader
        title="Taxonomy"
        description="Maintain exam blueprints, domains, books, chapters, knowledge points, and tags."
      />
      <RequirePermission
        perm="admin:manage_taxonomy"
        fallback={<EmptyState title="Not available" description="You need the manage-taxonomy permission to use this page." />}
      >
        <Tabs defaultValue="blueprints">
          <TabsList>
            <TabsTrigger value="blueprints">Blueprints &amp; domains</TabsTrigger>
            <TabsTrigger value="books">Books &amp; chapters</TabsTrigger>
            <TabsTrigger value="kps">Knowledge points</TabsTrigger>
            <TabsTrigger value="tags">Tags</TabsTrigger>
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
