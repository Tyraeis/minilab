{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "renovate.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "renovate.labels" -}}
helm.sh/chart: {{ include "renovate.chart" . }}
{{ include "renovate.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "renovate.selectorLabels" -}}
app.kubernetes.io/name: renovate
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
