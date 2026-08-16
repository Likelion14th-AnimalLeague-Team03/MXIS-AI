package com.mxis.ai.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.time.Instant;
import java.util.List;
import java.util.Map;

public final class MxisAiDtoSketch {
    private MxisAiDtoSketch() {}

    public record SensorReadingDto(
        Integer sequence,
        Long measuredAt,
        Double temperature,
        Double humidity,
        Double maxShock,
        Integer motionCount
    ) {}

    public record AiCareSummaryRequest(
        String productId,
        String productName,
        String deviceId,
        String materialId,
        List<String> materialSubtypes,
        String color,
        Integer analysisWindowDays,
        Integer samplingWindowSeconds,
        List<SensorReadingDto> sensorReadings,
        Map<String, Object> userEvents,
        Map<String, Object> userSymptoms,
        Map<String, Object> usageLog,
        LlmOptions llm
    ) {}

    public record LlmOptions(
        Boolean enabled,
        String model,
        String locale,
        List<String> screenContexts
    ) {}

    public record AiCareSummaryResponse(
        String schemaVersion,
        ProductBlock product,
        Map<String, Object> featureSummary,
        AiCareSummary aiCareSummary
    ) {}

    public record ProductBlock(
        String productId,
        String name,
        String material,
        List<String> materialSubtypes,
        String color
    ) {}

    public record AiCareSummary(
        Instant generatedAt,
        Integer analysisWindowDays,
        DataSufficiency dataSufficiency,
        ProductCondition productCondition,
        StressLabels stressLabels,
        CareDecision careDecision,
        Explanation explanation,
        Map<String, Object> llmCopy,
        CopyGeneration copyGeneration,
        ReservationCta reservationCta,
        Evidence evidence,
        Debug debug
    ) {}

    public record DataSufficiency(
        String status,
        String reason,
        Integer validReadingCount,
        Double coverageHours,
        Instant lastMeasuredAt,
        Instant lastSyncedAt
    ) {}

    public record ProductCondition(
        String label,
        Integer score,
        String primaryFactor,
        String summary
    ) {}

    public record StressLabels(
        String humidity,
        String temperatureHeat,
        String dryness,
        String handling,
        String usageRest,
        String uvLight
    ) {}

    public record CareDecision(
        String careNeed,
        String inspectionNeed,
        List<CareAction> recommendedActions,
        List<CareAction> doNotDo
    ) {}

    public record CareAction(
        String code,
        String title,
        String description,
        Integer priority,
        String category,
        String durationHint,
        Boolean isPrimary
    ) {}

    public record Explanation(
        @JsonProperty("short")
        String shortText,
        List<String> reasonBullets,
        List<String> sensorLimitations
    ) {}

    public record ReservationCta(
        Boolean recommended,
        String level,
        String title,
        String description,
        String suggestedServiceType,
        String prefillNote
    ) {}

    public record CopyGeneration(
        String source,
        String model,
        String error,
        String rawResponseId
    ) {}

    public record Evidence(
        List<String> matchedKbEntries,
        List<String> triggeredRules,
        String sourceLevel
    ) {}

    public record Debug(
        String featureVersion,
        String ruleVersion
    ) {}
}
