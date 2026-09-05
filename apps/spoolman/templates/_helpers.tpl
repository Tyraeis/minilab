{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "spoolman.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "spoolman.labels" -}}
helm.sh/chart: {{ include "spoolman.chart" . }}
{{ include "spoolman.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "spoolman.selectorLabels" -}}
app.kubernetes.io/name: "spoolman"
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
