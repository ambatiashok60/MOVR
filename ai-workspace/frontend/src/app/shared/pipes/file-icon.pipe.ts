import { Pipe, PipeTransform } from '@angular/core';

const ICON_BY_EXTENSION: Record<string, string> = {
  ts: 'pi pi-code',
  js: 'pi pi-code',
  py: 'pi pi-code',
  html: 'pi pi-code',
  scss: 'pi pi-palette',
  css: 'pi pi-palette',
  json: 'pi pi-file-edit',
  md: 'pi pi-file',
  yaml: 'pi pi-file',
  yml: 'pi pi-file',
  txt: 'pi pi-file',
};

@Pipe({ name: 'fileIcon', standalone: true })
export class FileIconPipe implements PipeTransform {
  transform(filePath: string | undefined | null): string {
    if (!filePath) return 'pi pi-file';
    const extension = filePath.split('.').pop()?.toLowerCase() ?? '';
    return ICON_BY_EXTENSION[extension] ?? 'pi pi-file';
  }
}
