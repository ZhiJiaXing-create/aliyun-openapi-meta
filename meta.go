package aliyunopenapimeta

import (
	"embed"
)

//go:embed metadatas
//go:embed descriptions
//go:embed products
var Metadatas embed.FS
