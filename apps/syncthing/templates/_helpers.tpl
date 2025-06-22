{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "syncthing.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "syncthing.labels" -}}
helm.sh/chart: {{ include "syncthing.chart" . }}
{{ include "syncthing.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "syncthing.selectorLabels" -}}
app.kubernetes.io/name: "syncthing"
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
