package aliyunopenapimeta

import (
	"embed"
)

//go:embed metadatas
//go:embed products
var Metadatas embed.FS
