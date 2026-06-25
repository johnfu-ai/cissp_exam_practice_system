"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useDomains } from "@/lib/api/taxonomy";
import { useCreateSession } from "@/lib/api/practice";
import { ApiError } from "@/lib/api";
import { trackSession } from "@/features/practice/session-tracker";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { toast } from "@/components/ui/sonner";
import type { Subset, SessionCreateInput } from "@/lib/api/types";

const ANY = "__any__";

/**
 * Launches a scoped re-practice session over a question subset
 * (wrong / bookmarked / needs_review). Backed by the existing
 * POST /api/practice/sessions API — no dedicated browse endpoint exists.
 */
export function SubsetLauncher({
  subset,
  title,
  description,
  emptyHint,
}: {
  subset: Subset;
  title: string;
  description: string;
  emptyHint: string;
}) {
  const router = useRouter();
  const [count, setCount] = useState(10);
  const [domainId, setDomainId] = useState<string | null>(null);
  const domains = useDomains();
  const create = useCreateSession();

  function start() {
    const payload: SessionCreateInput = { count, subset, order_mode: "random" };
    if (domainId) payload.domain_id = domainId;
    create.mutate(payload, {
      onSuccess: (s) => {
        trackSession(s.id);
        router.push(`/practice/sessions/${s.id}`);
      },
      onError: (e) => {
        if (e instanceof ApiError && e.status === 422) {
          toast.error(emptyHint);
        } else {
          toast.error("Could not start the session.");
        }
      },
    });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <p className="text-sm text-muted-foreground">{description}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor={`count-${subset}`}>Question count</Label>
            <Input
              id={`count-${subset}`}
              type="number"
              min={1}
              max={100}
              value={count}
              onChange={(e) => setCount(Math.max(1, Math.min(100, Number(e.target.value) || 1)))}
            />
          </div>
          <div className="space-y-1.5">
            <Label>Domain (optional)</Label>
            <Select
              value={domainId ?? ANY}
              onValueChange={(v) => setDomainId(v === ANY ? null : v)}
            >
              <SelectTrigger>
                <SelectValue placeholder="All domains" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ANY}>All domains</SelectItem>
                {domains.data?.map((d) => (
                  <SelectItem key={d.id} value={d.id}>
                    {d.number}. {d.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <Button onClick={start} disabled={create.isPending}>
          {create.isPending ? "Starting…" : "Start review session"}
        </Button>
      </CardContent>
    </Card>
  );
}
