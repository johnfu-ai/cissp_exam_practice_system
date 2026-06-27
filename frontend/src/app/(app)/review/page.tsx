"use client";

import { PageHeader } from "@/components/page-header";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { SubsetLauncher } from "@/features/review/subset-launcher";
import { useT } from "@/lib/i18n/provider";

export default function ReviewPage() {
  const t = useT();
  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <PageHeader
        eyebrow={t("review.eyebrow")}
        title={t("review.title")}
        description={t("review.description")}
      />
      <Tabs defaultValue="wrong">
        <TabsList>
          <TabsTrigger value="wrong">{t("review.wrong")}</TabsTrigger>
          <TabsTrigger value="bookmarked">{t("review.bookmarked")}</TabsTrigger>
          <TabsTrigger value="flagged">{t("review.flagged")}</TabsTrigger>
        </TabsList>
        <TabsContent value="wrong">
          <SubsetLauncher
            subset="wrong"
            title={t("review.wrongTitle")}
            description={t("review.wrongDesc")}
            emptyHint={t("review.wrongEmpty")}
          />
        </TabsContent>
        <TabsContent value="bookmarked">
          <SubsetLauncher
            subset="bookmarked"
            title={t("review.bookmarkedTitle")}
            description={t("review.bookmarkedDesc")}
            emptyHint={t("review.bookmarkedEmpty")}
          />
        </TabsContent>
        <TabsContent value="flagged">
          <SubsetLauncher
            subset="needs_review"
            title={t("review.flaggedTitle")}
            description={t("review.flaggedDesc")}
            emptyHint={t("review.flaggedEmpty")}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
