"use client";

import { PageHeader } from "@/components/page-header";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { SubsetLauncher } from "@/features/review/subset-launcher";

export default function ReviewPage() {
  return (
    <div>
      <PageHeader
        title="Review"
        description="Re-practice the questions that need your attention — wrong answers, bookmarks, and flagged items."
      />
      <Tabs defaultValue="wrong">
        <TabsList>
          <TabsTrigger value="wrong">Wrong questions</TabsTrigger>
          <TabsTrigger value="bookmarked">Bookmarked</TabsTrigger>
          <TabsTrigger value="flagged">Flagged</TabsTrigger>
        </TabsList>
        <TabsContent value="wrong">
          <SubsetLauncher
            subset="wrong"
            title="Wrong-question book"
            description="Questions you previously answered incorrectly. Re-practice to turn them around and mark them mastered."
            emptyHint="No wrong questions match this filter yet."
          />
        </TabsContent>
        <TabsContent value="bookmarked">
          <SubsetLauncher
            subset="bookmarked"
            title="Bookmarked questions"
            description="Questions you saved while practicing."
            emptyHint="You haven't bookmarked any questions yet."
          />
        </TabsContent>
        <TabsContent value="flagged">
          <SubsetLauncher
            subset="needs_review"
            title="Flagged for review"
            description="Questions you flagged to revisit later."
            emptyHint="You haven't flagged any questions yet."
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
